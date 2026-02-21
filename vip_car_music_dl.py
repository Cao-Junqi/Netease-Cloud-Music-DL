import os
import re
import time
import requests
import pyncm
from pyncm import apis
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError

class VipCarMusicDownloader:
    def __init__(self, save_dir, raw_cookie):
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        self._inject_global_cookie(raw_cookie)

    def _inject_global_cookie(self, raw_cookie):
        """【核心修复】底层 Session 劫持，强制注入 Cookie 字典"""
        session = pyncm.GetCurrentSession()
        # 清洗可能带有的请求头前缀
        clean_cookie = raw_cookie.replace('cookie:', '').replace('Cookie:', '').strip()
        
        for item in clean_cookie.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                # 强制挂载到网易云主域名
                session.cookies.set(k, v, domain='.music.163.com')
        
        # 验证鉴权状态
        user_info = apis.login.GetCurrentLoginStatus()
        if user_info.get('code') == 200 and user_info.get('profile'):
            print(f"[Info] 会话劫持成功！当前 VIP 账号: {user_info['profile']['nickname']}")
        else:
            print("[Error] 致命异常：Cookie 无效或已过期，强行执行将触发 44s 试听风控。")
            exit(1) # 鉴权失败直接中断，避免制造 44s 脏数据

    def sanitize_filename(self, filename):
        return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

    def embed_id3_tags(self, mp3_path, track_info):
        """【核心修复】ID3 元数据及封面注入"""
        try:
            # 获取元数据信息
            song_name = track_info.get('name', 'Unknown Title')
            artist_name = "/".join([ar['name'] for ar in track_info.get('ar', [])])
            album_name = track_info.get('al', {}).get('name', 'Unknown Album')
            pic_url = track_info.get('al', {}).get('picUrl', '')

            # 初始化或加载 ID3 容器
            try:
                audio = ID3(mp3_path)
            except ID3NoHeaderError:
                audio = ID3()

            # 写入基础文本元数据 (TIT2:标题, TPE1:歌手, TALB:专辑)
            audio.add(TIT2(encoding=3, text=song_name))
            audio.add(TPE1(encoding=3, text=artist_name))
            audio.add(TALB(encoding=3, text=album_name))

            # 抓取并写入封面图 (APIC)
            if pic_url:
                pic_res = requests.get(pic_url, timeout=5)
                if pic_res.status_code == 200:
                    audio.add(APIC(
                        encoding=3, 
                        mime='image/jpeg', 
                        type=3, 
                        desc='Cover', 
                        data=pic_res.content
                    ))
            
            # 保存元数据到文件 (v2_version=3 兼容绝大多数车机系统)
            audio.save(mp3_path, v2_version=3)
            print(f"  └─ [ID3] 元数据与封面嵌入成功")
            
        except Exception as e:
            print(f"  └─ [Error] ID3 写入异常: {e}")

    def run_pipeline(self, playlist_ids):
        for pid in playlist_ids:
            print(f"\n========== 开始处理歌单: {pid} ==========")
            try:
                pl_info = apis.playlist.GetPlaylistInfo(pid)
                track_ids = [str(t['id']) for t in pl_info['playlist']['trackIds']]
            except Exception as e:
                print(f"[Error] 歌单解析失败: {e}")
                continue

            for index, sid in enumerate(track_ids, 1):
                try:
                    # 1. 提取详细元数据 (用于命名和 ID3)
                    track_info = apis.track.GetTrackDetail([sid])['songs'][0]
                    safe_name = self.sanitize_filename(track_info['name'])
                    mp3_path = os.path.join(self.save_dir, f"{safe_name}.mp3")
                    lrc_path = os.path.join(self.save_dir, f"{safe_name}.lrc")
                    
                    print(f"[{index}/{len(track_ids)}] {safe_name}")

                    # 增量跳过
                    if os.path.exists(mp3_path):
                        print(f"  ├─ [-] 缓存命中，跳过下载")
                        continue

                    # 2. 获取 VIP 流媒体直链
                    audio_res = apis.track.GetTrackAudio([sid], bitrate=320000)['data'][0]
                    audio_url = audio_res.get('url')
                    
                    if not audio_url:
                        print(f"  ├─ [!] 音频直链被拒绝 (无版权/数字专辑)")
                        continue

                    # 3. 下载流媒体并进行边界校验 (体积拦截)
                    stream_res = requests.get(audio_url, stream=True, timeout=15)
                    content_length = int(stream_res.headers.get('Content-Length', 0))
                    
                    # 兜底方案：体积小于 1.5MB (约 1500000 bytes) 判定为 44s 试听片段
                    if content_length > 0 and content_length < 1500000:
                        print(f"  ├─ [!] 触发试听风控 (文件过小)，拒绝落地脏数据")
                        continue

                    if stream_res.status_code == 200:
                        with open(mp3_path, 'wb') as f:
                            for chunk in stream_res.iter_content(4096):
                                if chunk: f.write(chunk)
                        print(f"  ├─ [+] MP3 媒体流落地 (320kbps)")

                        # 4. 执行元数据注入
                        self.embed_id3_tags(mp3_path, track_info)

                        # 5. 下载车机兼容歌词
                        lrc_info = apis.track.GetTrackLyrics(sid)
                        if 'lrc' in lrc_info and 'lyric' in lrc_info['lrc']:
                            with open(lrc_path, 'w', encoding='utf-8') as f:
                                f.write(lrc_info['lrc']['lyric'])
                            print(f"  └─ [+] LRC 歌词挂载成功")
                            
                    time.sleep(1.5) # 防火墙节流

                except Exception as e:
                    print(f"  ├─ [Error] 轨道处理中断: {e}")

if __name__ == "__main__":
    # 【必须确保 Cookie 完整，特别是 MUSIC_U 字段】
    VIP_COOKIE = "MUSIC_U=填写凭证; __csrf=填写凭证;"
    
    target_dir = r"D:\music"
    target_playlists = [
        "8055396278", "12644048660", "17509429376", 
        "13860403439", "9364024209"
    ]
    
    app = VipCarMusicDownloader(target_dir, VIP_COOKIE)
    app.run_pipeline(target_playlists)
