# 🎬 Sentinel Demo Video — Script & Shot List

> **Format**: ≤ 3 minutes, MP4 1080p, hosted on YouTube (unlisted is fine — public for submission)
> **Audio**: English voiceover (Dr. Chloe)
> **Subtitles**: Burned-in English (SRT also exported)
> **UI**: Real Traditional-Chinese interface — keep authentic. Add English callouts as overlay where needed.
> **Tool suggestion**: OBS Studio for screen capture, CapCut / DaVinci Resolve for post-production.

---

## 1. UI element → English callout cheat sheet

When you record, you'll see these Chinese UI labels. Add overlay text boxes pointing at each (use the callout text below verbatim — it's already aligned with the narration):

| Where it appears | Chinese on screen | English overlay (add over UI) |
|---|---|---|
| Patient search page | 搜尋病人 | Search patients |
| Patient list badge | 慢性病 | Chronic condition |
| Patient list badge | 紅旗 (red) | Red flag (confirmed) |
| Heart layer section | 心臟層 | Patient heart layer |
| Heart layer tab | 問題 / 用藥 / 紅旗 / 基準 | Problems / Medications / Flags / Baselines |
| Flag chip (yellow) | 偶爾忘東西 to_observe | "Occasionally forgetful" — under observation |
| Flag chip (red) | 偶爾忘東西 confirmed | "Occasionally forgetful" — **confirmed** |
| Visit row button | 🔁 跑 AI 回顧 | 🔁 Run AI Retrospective Review |
| Review result panel header | AI 回顧結果 | AI Review Result |
| Review tab | 接診 / 分診 / 用藥審查 / 衛教 | Intake / Triage / Audit / Education |
| Audit finding (red) | 藥物拮抗 | Drug-drug antagonism |
| Pin button | 📌 加進 watchlist | 📌 Save to my watchlist |
| New-visit banner | 你過去學到的 N 條 | You learned N lesson(s) |
| New-visit form | 新就診 | New visit |
| Rx form dropdown | 分類 | Drug category |
| Rx form input | 藥名 | Drug name |
| Rx form input | 用法 | Frequency |

---

## 2. Three-act script (≈ 2 min 50 s)

### Cold open — 0:00 to 0:10
**On screen**: Title card (static, hand-made in CapCut)
```
The Sentinel
A MemoryAgent for clinical practice
Qwen Cloud Hackathon 2026 — Track 1 + 4
```
**Voiceover** (10 s):
> Family doctors lose information across visits. The Sentinel is a four-agent diagnostic layer built on Qwen3.7-max that does two things no single-visit AI does — it accumulates memory across visits, and it retrospectively trains the doctor.

---

### Act 1 — Auntie Wang's heart layer  (0:10 to 0:45)

**Shot 1** (0:10–0:18): Open https://47.84.230.19.nip.io/ → search "王" → click 王慧明.
**Voiceover**:
> Meet Auntie Wang. Sixty-eight, female. She's been to this clinic four times over nine months.

**Shot 2** (0:18–0:35): Patient detail page. Zoom-in / highlight on heart layer.
Overlay callouts on screen (use cheat sheet labels above):
- Point at "心臟層" → "Patient heart layer"
- Point at red flag "偶爾忘東西 confirmed" → "Occasionally forgetful — confirmed (was 'to_observe' on visit 3)"
- Point at chronic "高血壓" → "Hypertension"
- Point at long-term med "amlodipine" → "amlodipine"

**Voiceover**:
> The heart layer is the per-patient memory the system maintains automatically. One confirmed red flag, occasionally forgetful — escalated from "to observe" to "confirmed" when the symptom reappeared three visits later. One chronic problem, hypertension. One long-term medication, amlodipine. And a BP baseline trend across all four visits.

**Shot 3** (0:35–0:45): Scroll to visit timeline. Highlight visits 1 → 2 → 3 → 4.
**Voiceover**:
> All of this was built automatically — by what we call the post-visit evolution hook. We never asked the doctor to label anything.

---

### Act 2 — Mode A retrospective review (0:45 to 1:50)

**Shot 4** (0:45–0:55): Hover visit 4 row → click 「🔁 跑 AI 回顧」.
Overlay callout: "🔁 Run AI Retrospective Review".

**Voiceover**:
> Now the interesting part. We click "Run AI Retrospective Review" on visit four — when she came in with rebounded blood pressure, worsening forgetfulness, and a fall the week before.

**Shot 5** (0:55–1:10): Loading state (~30 s) — cut/timelapse to result panel. Show all 4 agent tabs.
**Voiceover**:
> The system reconstructs the patient's heart layer as it was at this visit — not as it is today. This is important: we want to know what was knowable then, not now. It also injects every prior visit's diagnosis and prescription as context, and runs four Qwen3.7-max agents in parallel.

**Shot 6** (1:10–1:30): Click the audit tab. Zoom on the red finding.
Overlay callout on the finding text: "Drug-drug antagonism: NSAIDs reduce amlodipine's antihypertensive effect"

**Voiceover**:
> Here it is. The audit agent flags it: the ibuprofen prescribed at visit three for knee pain is antagonizing the amlodipine. NSAIDs blunt the antihypertensive effect, and in elderly patients on antihypertensives, they can also cause kidney-mediated changes that contribute to falls. The doctor missed this across three visits. The AI surfaces it on a retrospective look.

**Shot 7** (1:30–1:50): Click 「📌 加進 watchlist」. Animate in a small confirmation toast or popup.
Overlay callout: "📌 Save to my watchlist".

**Voiceover**:
> One click — save this lesson to the doctor's watchlist. The pattern is extracted: NSAID plus calcium-channel-blocker interaction in elderly hypertensives. And the lesson text is saved.

---

### Act 3 — The retrospective coaching loop closes  (1:50 to 2:25)

**Shot 8** (1:50–2:05): Navigate to "新就診" / New visit page for a different patient.
Overlay callout: "Open a new visit — any patient".

**Voiceover**:
> Now the doctor opens a new visit for any other patient. Watch the top of the page.

**Shot 9** (2:05–2:25): Zoom on the watchlist banner at top of new-visit page.
Overlay callout on the banner: "📌 You learned 1 lesson: ibuprofen + amlodipine interaction"

**Voiceover**:
> There it is. The doctor's own past lesson, surfaced as a banner. The AI is retrospectively training the doctor — across patients, across time. This is the closed loop the Track 1 brief asks for: memory accumulates across visits, and retrospectively into doctor education.

---

### Track 4 cameo  (2:25 to 2:45)

**Shot 10** (2:25–2:45): Fast-cut montage of the new-visit form being filled in: SOAP fields → Rx form (category → drug → frequency → days).
**Voiceover**:
> A quick word on Track 4. The new-visit page is engineered to make Qwen do all the cognitive heavy lifting. The doctor types or dictates, picks prescriptions from a category-then-drug type-ahead, hits submit, and four agents run in parallel: intake, triage, audit, and education. Every output is persisted and replayable. The doctor stays with the patient.

---

### Outro  (2:45 to 3:00)

**Shot 11** (2:45–3:00): Architecture screen — show `deployment/architecture.md` rendered on GitHub.
**Voiceover**:
> Built on Alibaba Cloud — ECS in Singapore, OSS for asset backup, DashScope International for every Qwen3.7-max call. Code is MIT-licensed, deployed live at 47.84.230.19.nip.io. Sandbox data, fictional patients. Thanks for watching.

**End card** (last 2 s):
```
The Sentinel
github.com/<your-handle>/clinic-os-sentinel-v3
Qwen Cloud Hackathon 2026
```

---

## 3. Recording checklist (driver's run-of-show)

Before you start OBS:

- [ ] Browser at 1920×1080, F11 fullscreen, hide bookmarks bar
- [ ] Use **Chrome incognito** — clean profile, no extensions visible
- [ ] Pre-open the demo URL, navigate to `/sentinel/patients`, search 王, click into Auntie Wang once to warm caches
- [ ] Pre-trigger one Mode A review on a non-key visit so the second one (the real shot) loads with Qwen output already cached
- [ ] Microphone test: phone-pop filter or shirt collar
- [ ] Quiet room, cats not on the keyboard 😺
- [ ] OBS scene 1080p60, audio 44.1kHz mono

During recording:

- One take per **Shot** — easier to retry a single shot than re-record everything.
- For the Qwen loading shot (Shot 5), let it run live once for authenticity, then in post you can time-lapse the 30-second wait to 3 seconds.
- Speak about **20% slower than feels natural** — easier to subtitle, easier for non-native English judges.

After recording:

- [ ] Edit shots in CapCut / DaVinci.
- [ ] Add UI callouts (text boxes + arrows) per the cheat sheet in §1.
- [ ] Burn in English subtitles **and** export SRT separately.
- [ ] Add a 1-second medical disclaimer at the very bottom of every shot: *"Sandbox demonstration. Fictional patients. Not medical advice."*
- [ ] Total ≤ 2 min 55 s (safety margin under Devpost's 3-min hard cap).
- [ ] Export 1080p H.264, AAC audio.
- [ ] Upload to YouTube **public** (unlisted is technically OK but public is friendlier to judges).
- [ ] Title: *The Sentinel — Longitudinal Memory & Retrospective Coach (Qwen Cloud Hackathon 2026)*
- [ ] Pin YouTube link into the Devpost submission form.

---

## 4. If anything blows up live during recording

Common failures and where to look:

| Symptom | Likely cause | Fix |
|---|---|---|
| Caddy returns 502 on /api/* | backend container restarted, still on entrypoint alembic step | `ssh root@47.84.230.19 'cd /root/clinic-os-sentinel-v3/deployment && docker compose logs backend --tail 30'`; wait 30 s and retry |
| Mode A review hangs > 90 s | DashScope rate limit or timeout | refresh page; previous draft should be cached in `ai_drafts` |
| Watchlist banner doesn't show | banner only on new-visit page, not patient detail | go to a patient → "新就診" button |
| 4 agents return some missing fields | DashScope partial outage; rerun once | the system silently skips missing agents (best-effort) — usually filled on retry |

Worst case, fall back to recording the local dev server (port 8081); same demo, just localhost. Mention in the video description that the live demo is at the cloud URL.
