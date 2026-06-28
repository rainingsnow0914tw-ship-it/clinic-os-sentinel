# 🎬 Sentinel Demo — Recording Guide

> **取代** `VIDEO_SCRIPT.md` 給司機本人錄屏 + CapCut 用的完整 SOP。
> ≤ 3 分鐘、OBS 螢幕錄影、CapCut 剪接 + 旁白 + 字幕、中英對照、評審看得懂。

---

## 📋 兩條路自己選

| | 英文旁白（A 案）| 中文旁白（B 案）|
|---|---|---|
| **司機錄的話** | 念英文 voiceover 稿，3 min 約 350 詞 | 念中文 voiceover 稿，3 min 約 700 字 |
| **字幕怎麼放** | 中英雙行字幕（中文上、英文下）| 中英雙行字幕（中文上、英文下）|
| **規則合規** | ✅ 完美 | ✅ 旁白中文 + 英文 subtitle = 合規 |
| **適合誰** | 想顯逼真／英文流利時 | 念得最自然、最快收工 |

**推薦 B 案**：中文母語錄最自然，字幕補英文 = 規則 100% 合規。下面兩個版本的 voiceover 都附上，挑一個錄。

---

## 🎛️ §1. 錄影前準備（5 分鐘）

### 1.1 環境
- [ ] **瀏覽器 Chrome incognito 模式**（隱身視窗）— 清乾淨沒擴充
- [ ] 視窗最大化 **1920×1080**（按 F11 全螢幕，或拖到 1080p）
- [ ] 隱藏書籤列（Ctrl+Shift+B）
- [ ] **預先打開 https://47.84.230.19.nip.io/** → 搜尋「王」一次 → 點王慧明 → 點任一 visit 「🔁 跑 AI 回顧」一次（讓 Qwen 暖機、之後正式錄第二次會快）
- [ ] **背景音樂**：CapCut 後製加 royalty-free 輕音樂（音量 -20dB 不蓋過旁白）
- [ ] 麥克風測試：用手機耳麥就好、距嘴 10 cm、避免噴麥
- [ ] 房間關門、貓不能上鍵盤 😺

### 1.2 OBS（或 Windows + G 螢幕錄影）
- [ ] **解析度 1920×1080 / 60fps**
- [ ] **音訊 mono 44.1 kHz**
- [ ] 錄製格式 **mp4 (H.264)**
- [ ] 一個 take 錄整個 demo（NG 不用重來，CapCut 剪掉即可）

---

## 🎬 §2. 三幕分鏡 + voiceover + 字幕

> 「📺」= 螢幕該對哪 / 該點什麼
> 「🎤 EN」= 英文版 voiceover（A 案唸的）
> 「🎤 ZH」= 中文版 voiceover（B 案唸的）
> 「💬」= 字幕（中文上、英文下，**兩條同步顯示**）

---

### 🎬 Act 0 — Cold open（0:00 – 0:08, 8 秒）

📺 **靜態 title card**（CapCut 後製做，純背景 + 字）：
```
🛡️ The Sentinel
A MemoryAgent for clinical practice
Qwen Cloud Hackathon 2026 — Track 1 + 4
```

🎤 **EN**（英文版）:
> Family doctors lose information across visits. We built **The Sentinel** — a four-agent diagnostic layer on Qwen3.7-max that closes the loop.

🎤 **ZH**（中文版）:
> 家庭醫師看診的時候，常常會把過去的線索弄丟。我們做了一個叫做「哨兵」的系統 — 用四個 Qwen3.7-max agent，把這個漏洞補起來。

💬 **字幕（兩行同時顯示）**:
```
家庭醫師看診時常把過去線索弄丟，我們做了「哨兵」把它補起來
Family doctors lose info across visits — The Sentinel closes that loop
```

---

### 🎬 Act 1 — Auntie Wang's heart layer（0:08 – 0:40, 32 秒）

📺 開始錄屏 → 打開 https://47.84.230.19.nip.io/ → 點頂部金色 **⭐ Track 1 demo patient · 王阿姨四幕劇** banner → 直接跳王阿姨病例頁。（不用搜尋，banner 是 hackathon demo 特製置頂入口）

🎤 **EN**:
> Meet Auntie Wang. Sixty-eight, female. She's been to this clinic four times over nine months.

🎤 **ZH**:
> 認識一下王阿姨。68 歲，女性。九個月內來這家診所看了四次。

💬:
```
認識王阿姨：68 歲女性，九個月內看了四次診
Meet Auntie Wang, 68 F, four visits over nine months
```

---

📺 病例頁 zoom-in / 滑鼠停在心臟層上半 — 紅旗、慢性病、長期用藥區。

🎤 **EN**:
> Look at her heart layer. **One confirmed red flag** — occasional forgetfulness, first observed at visit 2026-02-15, confirmed at visit 2026-06-26. **One chronic problem** — hypertension, diagnosed at visit 2025-09-20. **One long-term medication** — amlodipine. **And a BP baseline across all four visits.** Notice every entry shows the visit it came from. We'll need that in a moment.

🎤 **ZH**:
> 看一下她的心臟層。**一個確認的紅旗** — 偶爾忘東西，首次觀察是 2026-02-15、確認是 2026-06-26。**一個慢性病** — 高血壓，2025-09-20 診斷。**一個長期用藥** — amlodipine。**跨四次就診的血壓基線**。注意每一條都標了出處的就診日期。等下要用到。

💬（三段、跟著 voiceover 切換）:
```
一個確認紅旗：偶爾忘東西
One confirmed red flag: occasionally forgetful
```
```
一個慢性病高血壓，一個長期用藥 amlodipine
One chronic problem: hypertension; one long-term med: amlodipine
```
```
血壓基線跨四次就診
BP baseline tracked across all four visits
```

---

📺 滑鼠下滑到「📅 就診歷史」section、視覺 highlight 4 個 visit row。

🎤 **EN**:
> This entire memory was built **automatically**. We never asked the doctor to label anything. Every visit auto-evolves the heart layer.

🎤 **ZH**:
> 這整套記憶 **完全是自動產生的**。我們從來沒要求醫師標任何東西。每一次就診都會自動演進這個心臟層。

💬:
```
整套心臟層完全自動產生，醫師不用標任何東西
The heart layer is built automatically — no doctor labeling required
```

---

### 🎬 Act 2 — Mode A retrospective review（0:40 – 1:50, 70 秒）

📺 hover 第 4 個 visit（2026-06-26 那次）→ 點藍色按鈕「🔁 跑 AI 回顧 / Run AI Retrospective Review」。

🎤 **EN**:
> Now the interesting part. **We click "Run AI Retrospective Review" on visit four** — when she came in with rebounded BP, worsening forgetfulness, and a fall last week.

🎤 **ZH**:
> 現在重點來了。**我們在第四次就診點下「跑 AI 回顧」** — 那次她血壓反彈、健忘變嚴重、上週還跌了一跤。

💬:
```
重點：在第四次就診點下「跑 AI 回顧」
We click "Run AI Retrospective Review" on visit 4
```

---

📺 看 loading 畫面（CapCut 後製把 30 秒 loading 時間軸 **加速到 3 秒**、加個 ⏳ tick 動畫）。

🎤 **EN**:
> The system reconstructs the heart layer **as it was at that visit** — not as it is today. And it **shows you what it excluded**. Right in the summary panel: *the forgetfulness flag was first observed only on 2026-02-15, so for an earlier visit it's filtered out. Nine BP measurements after this visit are excluded.* The AI literally cannot see them. This is the no-hindsight guarantee, **visible in the UI, not just claimed**.

🎤 **ZH**:
> 系統把心臟層 **還原到那次就診當下的樣子** — 而且 **告訴你它過濾掉了什麼**。Summary panel 直接列出來：「偶爾忘東西這個紅旗是 2026-02-15 才出現的、早一點的就診看不到。九筆之後的血壓測量也排除掉了。」AI 真的看不見這些東西。「沒有先知能力」這件事是 **UI 直接證明，不是用嘴講**。

💬（兩段）:
```
系統還原心臟層到那次就診當下，不用今天視角
System reconstructs heart layer AS IT WAS at that visit — no hindsight
```
```
注入過去所有就診上下文，四個 Qwen3.7-max agent 並行跑
Injects all prior visits as context; 4 Qwen3.7-max agents run in parallel
```

---

📺 結果出來、點 audit 那個 tab（🛡️ 後閘門 / Audit agent）→ zoom 紅色 finding 文字。

🎤 **EN**:
> Here it is. The **Audit agent flags it**: the ibuprofen prescribed at visit three is **antagonizing the amlodipine**. NSAIDs blunt the antihypertensive effect, and in elderly patients on antihypertensives, they can also contribute to falls. **The doctor missed this across three visits.** The AI surfaces it on a retrospective look.

🎤 **ZH**:
> 它出現了。**Audit agent 抓到了**：第三次就診開的 ibuprofen **正在拮抗 amlodipine**。NSAID 會削弱降壓藥效，老年人吃降壓藥再加 NSAID，還可能造成跌倒。**這個盲點橫跨三次就診醫師都沒抓到**。AI 一回顧就找出來了。

💬（拆兩段）:
```
Audit agent 抓到：ibuprofen 拮抗 amlodipine
Audit agent finds: ibuprofen antagonizes amlodipine
```
```
這個盲點橫跨三次就診醫師都沒抓到，AI 一回顧就找出來
The doctor missed this across 3 visits — AI surfaced it retrospectively
```

---

### 🎬 Act 3 — Watchlist reverse-training（1:50 – 2:25, 35 秒）

📺 滑鼠移到「📌 把這個教訓加進我的 watchlist / Save this lesson to my watchlist」按鈕 → 點 → 看綠色確認 message。

🎤 **EN**:
> **One click** — save this lesson to the doctor's watchlist. The system extracts the pattern and the lesson text.

🎤 **ZH**:
> **一鍵** — 把這個教訓加進醫師的 watchlist。系統會自動萃取 pattern 和教訓文字。

💬:
```
一鍵加進醫師 watchlist，系統自動萃取 pattern 跟教訓
One click → saves pattern + lesson text to doctor's watchlist
```

---

📺 點 ← 回搜尋 → 隨便選另一個病人 → 點右上「➕ 新就診 / New Visit」按鈕。

🎤 **EN**:
> Now the doctor opens a new visit for **any other patient**. Watch the top of the page.

🎤 **ZH**:
> 現在醫師為 **任何別的病人** 開新就診。注意看頁面頂部。

💬:
```
醫師為任何別的病人開新就診，看頁面頂部
Doctor opens a new visit for ANY other patient — watch the top
```

---

📺 zoom 頁面頂部的 watchlist banner（橘色或藍色框、顯示「📌 你過去學到的 / Your past lessons」+ ibuprofen×amlodipine pattern）。

🎤 **EN**:
> There. **The doctor's own past lesson, surfaced as a banner.** The AI is retrospectively training the doctor — across patients, across time. This is the closed loop the Track 1 brief asks for.

🎤 **ZH**:
> 看到了。**醫師自己過去學到的教訓，以 banner 形式出現**。AI 正在反向訓練這個醫師 — 跨病人、跨時間。這就是 Track 1 要求的閉環。

💬:
```
醫師過去學到的教訓自動 banner 顯示，AI 跨病人跨時間反訓練醫師
Past lesson auto-surfaces as a banner — AI reverse-trains the doctor
```

---

### 🎬 Act 4 — Track 4 Autopilot cameo（2:25 – 2:50, 25 秒）

📺 快速 cut 蒙太奇：點開新就診 form → 隨便填 CC / HPI → 滾到 Rx form → 點分類下拉 → 選一個藥 → 點「🤖 跑 AI 建議 / Run AI Suggestions」 → 看 4 agent panel 跳出來。

🎤 **EN**:
> Quick note on Track 4. The new-visit page makes Qwen do all the heavy lifting. The doctor types, picks prescriptions from a category dropdown, hits submit. **Four agents run in parallel** — intake, triage, audit, education. Every output persisted, every reasoning replayable.

🎤 **ZH**:
> Track 4 簡單說一下。新就診頁讓 Qwen 做所有認知重活。醫師打字、處方從分類下拉選、按送出。**四個 agent 並行跑** — 接診、分診、用藥審查、衛教。每個輸出都存下來、每個推理都可以回看。

💬:
```
Track 4：新就診頁四個 agent 並行 Qwen3.7-max，每個推理可回看
Track 4: new-visit page fans out 4 agents in parallel, all replayable
```

---

### 🎬 Outro（2:50 – 3:00, 10 秒）

📺 切到一個 architecture 簡圖（CapCut 後製做 — 三個方塊：ECS / OSS / DashScope，標 "Singapore region"）。

🎤 **EN**:
> Built on Alibaba Cloud — ECS, OSS, DashScope Qwen3.7-max, all in the Singapore region. Code MIT-licensed. Sandbox data, fictional patients. Thanks for watching.

🎤 **ZH**:
> 整個系統跑在阿里雲上 — ECS、OSS、DashScope Qwen3.7-max，全在新加坡 region。代碼 MIT 授權。沙盒資料、虛構病人。謝謝觀看。

💬:
```
阿里雲新加坡 ECS+OSS+Qwen3.7-max，MIT 授權，沙盒虛構資料
On Alibaba Cloud Singapore: ECS+OSS+Qwen3.7-max. MIT license. Fictional data.
```

---

📺 **End card**（CapCut 後製 2 秒）：
```
🛡️ The Sentinel
https://47.84.230.19.nip.io/
github.com/<your-handle>/clinic-os-sentinel-v3
Qwen Cloud Hackathon 2026
```

---

## 🎞️ §3. CapCut 後製步驟（建議順序）

### 3.1 import + 粗剪
1. 開新 project → 1080p 60fps → 拖入 OBS 錄好的 mp4。
2. 在時間軸把每個動作不流暢的地方（誤點、長 loading、卡頓）**剪掉**。
3. 把 Mode A loading 那 30 秒 → 用「**speed**」工具加速 10×（剩 3 秒）+ 加 ⏳ 浮動 emoji 動畫。

### 3.2 旁白
1. **內錄 voiceover**：CapCut 有「Record」功能，跟著上面 §2 的 voiceover 稿一句一句錄。
2. 不順就重錄那一句、CapCut 可以多 take。
3. **錄完降噪**：CapCut → Audio → Noise Reduction（一鍵）。
4. **音量**：voiceover 軌道 0 dB（最大），背景音樂軌 -22 dB。

### 3.3 字幕（中英對照）
1. CapCut 有「**自動字幕**」功能 — 跑自動產生中文（或英文）字幕。
2. 自動字幕對到 voiceover 時間軸後，**手動逐句改成雙行**：
   - 上行：中文
   - 下行：英文
3. 用上面 §2「💬」每段對齊（時間碼跟著 voiceover 走）。
4. 字幕字體大小：中文 36pt、英文 28pt；位置底部、留 80px 邊距。
5. 描邊：黑色 2px stroke（讓白字在任何畫面都看清楚）。

### 3.4 加 title / end / overlay
1. **Title card**（0:00-0:08）：CapCut Text template 隨便挑一個。
2. **Architecture 結尾圖**（2:50-3:00）：CapCut 內建圖庫 + 3 個方塊文字。
3. **End card**（最後 2 秒）：純黑底 + URL + GitHub。

### 3.5 export
- 格式 **MP4 (H.264)**
- 解析度 **1080p**
- 幀率 **30 fps** 夠（OBS 錄 60 但 export 30 省檔）
- 音訊 **AAC 192 kbps mono**
- 預估檔案大小 100-200 MB

### 3.6 上傳 YouTube
- title: `The Sentinel — Longitudinal Memory & Retrospective Coach (Qwen Cloud Hackathon 2026)`
- description（用 `DEVPOST_SUBMISSION.md` 的 "What it does" 段貼進去）
- **設「公開」**（hackathon 評審需要能訪問）
- 拿到 URL 後填進 Devpost form

---

## 📋 §4. SRT 字幕完整檔（可直接 import 進 CapCut）

> 兩個 SRT 檔分開存：`sentinel-zh.srt` 跟 `sentinel-en.srt`。
> CapCut 可以同時 import 兩條字幕軌、上下排列。
> 時間碼是粗估的、實際根據你 voiceover 速度微調。

### 4.1 `sentinel-zh.srt`
```srt
1
00:00:00,500 --> 00:00:08,000
家庭醫師看診時常把過去線索弄丟，我們做了「哨兵」把它補起來

2
00:00:08,500 --> 00:00:14,000
認識王阿姨：68 歲女性，九個月內看了四次診

3
00:00:14,500 --> 00:00:20,000
一個確認紅旗：偶爾忘東西

4
00:00:20,500 --> 00:00:26,000
一個慢性病高血壓，一個長期用藥 amlodipine

5
00:00:26,500 --> 00:00:32,000
血壓基線跨四次就診

6
00:00:32,500 --> 00:00:40,000
整套心臟層完全自動產生，醫師不用標任何東西

7
00:00:40,500 --> 00:00:48,000
重點：在第四次就診點下「跑 AI 回顧」

8
00:00:48,500 --> 00:01:05,000
系統還原心臟層到那次就診當下，不用今天視角

9
00:01:05,500 --> 00:01:20,000
注入過去所有就診上下文，四個 Qwen3.7-max agent 並行跑

10
00:01:20,500 --> 00:01:35,000
Audit agent 抓到：ibuprofen 拮抗 amlodipine

11
00:01:35,500 --> 00:01:50,000
這個盲點橫跨三次就診醫師都沒抓到，AI 一回顧就找出來

12
00:01:50,500 --> 00:02:00,000
一鍵加進醫師 watchlist，系統自動萃取 pattern 跟教訓

13
00:02:00,500 --> 00:02:10,000
醫師為任何別的病人開新就診，看頁面頂部

14
00:02:10,500 --> 00:02:25,000
醫師過去學到的教訓自動 banner 顯示，AI 跨病人跨時間反訓練醫師

15
00:02:25,500 --> 00:02:50,000
Track 4：新就診頁四個 agent 並行 Qwen3.7-max，每個推理可回看

16
00:02:50,500 --> 00:03:00,000
阿里雲新加坡 ECS+OSS+Qwen3.7-max，MIT 授權，沙盒虛構資料
```

### 4.2 `sentinel-en.srt`
```srt
1
00:00:00,500 --> 00:00:08,000
Family doctors lose info across visits — The Sentinel closes that loop

2
00:00:08,500 --> 00:00:14,000
Meet Auntie Wang, 68 F, four visits over nine months

3
00:00:14,500 --> 00:00:20,000
One confirmed red flag: occasionally forgetful

4
00:00:20,500 --> 00:00:26,000
One chronic problem: hypertension; one long-term med: amlodipine

5
00:00:26,500 --> 00:00:32,000
BP baseline tracked across all four visits

6
00:00:32,500 --> 00:00:40,000
The heart layer is built automatically — no doctor labeling required

7
00:00:40,500 --> 00:00:48,000
We click "Run AI Retrospective Review" on visit 4

8
00:00:48,500 --> 00:01:05,000
System reconstructs heart layer AS IT WAS at that visit — no hindsight

9
00:01:05,500 --> 00:01:20,000
Injects all prior visits as context; 4 Qwen3.7-max agents run in parallel

10
00:01:20,500 --> 00:01:35,000
Audit agent finds: ibuprofen antagonizes amlodipine

11
00:01:35,500 --> 00:01:50,000
The doctor missed this across 3 visits — AI surfaced it retrospectively

12
00:01:50,500 --> 00:02:00,000
One click → saves pattern + lesson text to doctor's watchlist

13
00:02:00,500 --> 00:02:10,000
Doctor opens a new visit for ANY other patient — watch the top

14
00:02:10,500 --> 00:02:25,000
Past lesson auto-surfaces as a banner — AI reverse-trains the doctor

15
00:02:25,500 --> 00:02:50,000
Track 4: new-visit page fans out 4 agents in parallel, all replayable

16
00:02:50,500 --> 00:03:00,000
On Alibaba Cloud Singapore: ECS+OSS+Qwen3.7-max. MIT license. Fictional data.
```

---

## ✅ §5. 出片前最後 checklist

- [ ] 總長 ≤ **2:55**（安全 margin 不超過 3:00 hard cap）
- [ ] **每個畫面動作可以被字幕 + voiceover 解釋**（評審看英文字幕就懂）
- [ ] 王阿姨那組 demo 動作 **每一個元素都至少有英文字幕一次提到**
- [ ] **disclaimer**：影片最後 2 秒或 description 第一行寫
  > Sandbox demonstration. Fictional patient data. Not medical advice.
- [ ] 影片描述（YouTube）開頭直接貼 `DEVPOST_SUBMISSION.md` 的 "What it does" 那段
- [ ] **YouTube 設為公開（Public）**，不是 unlisted
- [ ] 拿到 YouTube URL → 填進 Devpost submission form

---

## 🎬 §6. 如果錄出包了怎麼辦（救急表）

| 症狀 | 對策 |
|---|---|
| 「跑 AI 回顧」按下去 504 timeout | refresh → 再點一次。雲端 backend 可能 cold start，第二次會快 |
| Qwen 回應卡 60+ 秒 | OBS 繼續錄、CapCut 後製把它 speed 10× 變 6 秒 |
| 念英文卡了一句 | 整個影片不用重錄，那一句單獨 voice-over 重錄、CapCut 拼上去就好 |
| 動作點錯了 | 不用重錄，CapCut 剪刀工具把錯誤段剪掉、後一段往前接 |
| 中文字幕 CapCut 自動產生對不上 voiceover | 直接 import 上面 §4 的 `.srt` 檔覆蓋 |
