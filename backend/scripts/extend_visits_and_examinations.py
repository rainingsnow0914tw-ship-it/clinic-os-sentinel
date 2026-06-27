"""
============================================================
scripts/extend_visits_and_examinations.py -- 補 visit + examination dataset
============================================================
Phase 3 frontend 上後司機反饋「點開大部分病人都空白」-- 因為 jimmy 60 個
patient 只有 5 個 visit、我擴的 40 個新 patient 一個 visit 都沒有。

本 script 為**每個 patient** 生 1-3 個 visit + 對應 visit_examination
(vital signs / lab results 結構化)、根據 patient 慢性病做 chronic-aware
disease-specific 主訴 / 診斷 / 數據 (例：高血壓 BP 偏高、糖尿病 HbA1c 偏高)。

直接對 DB 操作 (不走 jimmy mock → seed_dev_data)、idempotent:
  - source='extended_mock' 區隔 jimmy 'mock'
  - 重跑會先刪 source='extended_mock' 再灌
  - reset_dev_data 守門 source='mock' 不會誤砍

用法:
    ENVIRONMENT=dev python -m scripts.extend_visits_and_examinations
    ENVIRONMENT=dev python -m scripts.extend_visits_and_examinations --dry-run
============================================================
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Patient,
    PatientProblem,
    User,
    Visit,
    VisitExamination,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")
log = logging.getLogger("extend_visits")

SEED = 20260627
SOURCE_TAG = "extended_mock"


# ─────────────────────────────────────────────────────────
# Chronic-aware pools
# ─────────────────────────────────────────────────────────

# 4-tuple: (chief_complaint, hpi, physical_exam, diagnosis)
# 司機示範真實診所手寫病歷, SOAP-like 結構必須有 HPI (現病史) + PE (查體)
# HPI 用病程記述風格、PE 用醫師簡寫風格 (神清/咽紅/肺音清/腹軟/...)

CHRONIC_CASES: dict[str, list[tuple[str, str, str, str]]] = {
    "Hypertension": [
        ("頭痛 2 天", "病人有高血壓病史多年, 2 天前出現後腦脹痛, 晨起明顯, 無噁心嘔吐, 自測 BP 158/95, 平時規律服 amlodipine 5mg qd", "神清, BP 158/95, HR 78, 心音清晰、無雜音, 雙肺呼吸音清, 雙下肢無水腫", "原發性高血壓 (未達標)"),
        ("後腦痛 早上明顯 1 週", "高血壓控制中病人, 近 1 週晨起後腦脹痛, 持續 1-2 hr 自行緩解, 自測 BP 晨間 162/98, 否認頭暈惡心", "神清, BP 165/100, HR 82, 心律規則, 肺音清, 神經學檢查無局灶徵象", "原發性高血壓 (控制不佳)"),
        ("自測 BP 偏高 1 週", "病人 1 週前家測 BP 多次 145-155/90-95, 無明顯不適, 否認頭痛胸悶, 平時服 amlodipine 5mg qd 已 2 年", "神清, BP 148/92, HR 76, 心肺正常, 無水腫", "原發性高血壓 (控制中)"),
        ("頭暈 3 天 起身明顯", "病人 3 天前出現姿勢性頭暈, 起身時明顯, 平躺後緩解, 無耳鳴聽力改變, 服用 BP 藥物史明確", "神清, 臥位 BP 145/88, 立位 1 min BP 122/76 (drop >20), HR 改變不大, 心肺正常", "原發性高血壓 (姿勢性低血壓需排除)"),
        ("頸部僵硬 + 頭痛 1 週", "病人 1 週前因工作壓力大開始出現頸肩僵硬伴後腦脹痛, BP 自測偏高, 否認外傷史", "神清, BP 156/94, HR 80, 頸部肌肉緊張壓痛 (+), 神經學檢查正常, 心肺正常", "原發性高血壓 (緊張型頭痛合併)"),
    ],
    "Type 2 Diabetes": [
        ("口渴 頻尿 加重 2 週", "T2DM 病人 2 週前出現口渴加重, 夜尿增 3-4 次, 體重未明顯改變, 自測空腹血糖 180-200 mg/dL, 平時服 metformin 500mg bid", "神清, BMI 27, 黏膜濕潤, 無酮味, 雙下肢周邊感覺對稱, 足部無潰瘍", "第二型糖尿病 (HbA1c 偏高)"),
        ("腳麻 1 個月", "T2DM 病史 8 年病人, 1 個月來雙足麻木呈襪套狀, 夜間明顯, 否認外傷或腰痛", "神清, 雙下肢遠端針刺覺減退至踝上, 振動覺對稱減弱, 足背動脈搏動可及, 無傷口", "第二型糖尿病 + 周邊神經病變"),
        ("視力模糊 1 個月", "T2DM 病史 5 年病人, 近 1 個月雙眼視力波動模糊, 無紅痛, 否認頭痛, 血糖控制 HbA1c 8.2%", "神清, 對話視力雙眼模糊, 視野粗測無缺損, 結膜無充血, 需轉眼科散瞳查眼底", "第二型糖尿病 (需轉介眼科檢視網膜)"),
        ("傷口不癒合 2 週", "T2DM 病人 2 週前右足底擦傷, 自行換藥未癒, 近 3 天傷口周圍紅腫滲液, 否認發燒", "神清, T 37.4, 右足底 1.5cm 潰瘍, 周圍紅腫熱, 滲淡黃膿液, 足背搏動可及", "第二型糖尿病 (血糖控制不佳 + 傷口感染)"),
        ("疲倦 3 週 + 夜尿增加", "T2DM 病人近 3 週疲倦感加重, 夜尿 3-4 次, 自測空腹 BG 約 160, 餐後 250, 服藥規律", "神清, BMI 28, 血壓 138/85, 心肺正常, 雙下肢無水腫, 黏膜濕潤", "第二型糖尿病 (血糖控制不佳)"),
    ],
    "Hyperlipidemia": [
        ("健檢 LDL 偏高 (家屬建議來)", "病人最近健檢 LDL 178 mg/dL, 無症狀, 家族有冠心病史, 飲食 BMI 偏高, 否認吸菸", "神清, BMI 27.5, BP 132/82, 心肺正常, 頸動脈雜音 (-), 無黃色瘤", "高血脂症 (新診)"),
        ("胸悶 偶發 1 週", "高血脂症服 statin 1 年病人, 1 週前出現勞動後胸悶, 約 3-5 min 緩解, 否認大汗放射痛", "神清, BP 138/85, HR 76, 心律規則, 無雜音, 肺音清, 需安排 ECG + 運動測試排除心因性", "高血脂症 (Statin 治療中, 排除心因性)"),
    ],
    "Asthma": [
        ("夜咳 1 週", "氣喘病史病人, 1 週來夜間 2-3 點咳嗽發作, 無痰, 早上緩解, 日間活動正常, 近期天氣轉涼", "神清, RR 18, SpO2 97%, 雙肺呼氣相延長, 散在哮鳴音, 心律規則", "氣喘 (夜間發作型)"),
        ("喘 2 天 加重", "氣喘控制中病人, 2 天前感冒後喘加重, 吸 SABA 緩解時間縮短, 夜間需起來坐, 否認胸痛發燒", "神清, RR 24, SpO2 93%, 雙肺廣泛哮鳴音, 呼氣相明顯延長, 輔助呼吸肌使用", "氣喘 急性發作"),
        ("氣短 爬樓梯時 3 天", "氣喘穩定病人 3 天前運動誘發氣短, 上 3 層樓即喘, 休息可緩解, 否認胸痛、無夜間發作", "神清, RR 20, SpO2 96%, 雙肺呼吸音清, 偶聞哮鳴音, 心律規則", "氣喘 (穩定追蹤、運動誘發)"),
        ("胸悶 一週", "氣喘病史病人 1 週來持續胸悶感, 否認喘鳴, 服 ICS 規律, 否認上呼吸道感染", "神清, BP 122/78, RR 18, SpO2 97%, 雙肺呼吸音清, 心律規則無雜音", "氣喘 (穩定追蹤)"),
    ],
    "COPD": [
        ("喘 加重 1 週", "COPD 病人 1 週前喘加重, 痰量增加但顏色未變, 否認發燒, 平時服 tiotropium qd", "神清, RR 22, SpO2 92%, 桶狀胸, 雙肺呼氣相延長, 散在乾濕囉音, 雙下肢無水腫", "COPD 急性惡化 (mild)"),
        ("咳嗽 帶痰 黃綠 2 週", "COPD 病人 2 週前咳嗽加重, 痰由白轉黃綠, 量增, 伴低熱 37.8, 喘加重", "神清, T 37.6, RR 24, SpO2 90%, 雙肺呼吸音減弱, 散在濕囉音, 心律規則", "COPD 急性惡化 (細菌感染合併)"),
        ("夜間呼吸困難 3 天", "COPD 病人近 3 天夜間平躺呼吸困難, 需墊高枕頭, 否認胸痛, 平時運動耐受性下降", "神清, RR 20, SpO2 91%, 端坐位舒適, 雙肺呼吸音減弱, 心音遙遠, 下肢輕度水腫", "COPD (穩定、需評估 SpO2)"),
    ],
    "Osteoarthritis": [
        ("膝痛 加重 1 週", "OA 病人 1 週前右膝痛加重, 上下樓梯明顯, 平地行走可, 否認外傷, 服用止痛藥短暫緩解", "神清, 步態跛行, 右膝關節輕度腫脹, 觸痛 (+), ROM 屈曲受限約 110°, 無發熱", "膝部骨關節炎 (急性發作)"),
        ("上下樓梯腳痛 5 天", "OA 病人 5 天來上下樓梯時雙膝疼痛, 平地行走無明顯不適, 否認晨僵超過 30 min", "神清, 雙膝關節輕度骨性肥大, 觸痛 (+), ROM 正常, 無腫脹發熱", "膝部骨關節炎"),
        ("關節僵硬 早上明顯", "OA 病人近期晨間雙手手指及膝關節僵硬約 15-20 min 可緩解, 活動後改善, 否認紅腫", "神清, 雙手 DIP/PIP 關節輕度骨性肥大, 無紅腫熱, 雙膝關節輕度捻髮音", "膝部骨關節炎 (晨僵)"),
    ],
    "Atrial Fibrillation": [
        ("心悸 3 天", "AF 病人 3 天前自覺心悸發作頻繁, 否認胸痛喘, 服 apixaban + bisoprolol 規律", "神清, BP 128/78, HR 92 不規律, 心律絕對不齊, 心音強弱不一, 肺音清", "心房顫動 (rate-controlled, 抗凝血藥追蹤)"),
        ("胸悶 偶發 1 週", "新發疑似 AF 病人, 1 週來陣發性胸悶心悸, 持續 10-30 min 自行緩解, 否認暈厥", "神清, BP 130/82, HR 110 不規律, 心律絕對不齊, 心音強弱不一, 雙下肢無水腫", "心房顫動 (新發、需排除心衰)"),
        ("頭暈 1 週 + 疲倦", "AF 病史病人 1 週來頭暈疲倦, 活動後加重, 否認暈厥胸痛, 服 bisoprolol 但 HR 仍偏快", "神清, BP 118/72, HR 115 不規律, 心音強弱不一, 肺音清, 雙下肢無水腫", "心房顫動 (rate 控制不佳)"),
    ],
    "CKD Stage 3": [
        ("下肢水腫 3 天", "CKD Stage 3 病人 3 天前出現雙下肢水腫加重, 體重增 2kg, 尿量略減, 否認喘", "神清, BP 142/88, HR 78, 心肺正常, 雙下肢凹陷性水腫 ++, 腹軟無壓痛", "慢性腎臟病第三期 (水腫加重)"),
        ("尿量減少 1 週", "CKD Stage 3 病人 1 週來尿量減 (約 1000ml/d), 近期天熱出汗多, 飲水偏少", "神清, BP 135/82, HR 88, 黏膜略乾, 皮膚彈性稍差, 雙下肢無水腫", "慢性腎臟病第三期 (脫水可能)"),
        ("疲倦 3 週 + 夜尿增加", "CKD 病人 3 週來疲倦加重, 夜尿 3 次, 否認血尿, 服降壓藥規律", "神清, BP 138/85, 結膜略蒼白, 心肺正常, 雙下肢輕度水腫", "慢性腎臟病第三期 (穩定追蹤)"),
    ],
    "Hypothyroidism": [
        ("疲倦 1 個月", "甲狀腺低下病人 1 個月來疲倦明顯, 體重略增, 怕冷, 服 levothyroxine 50mcg qd", "神清反應稍遲, BP 118/72, HR 58, 甲狀腺未觸及腫大, 皮膚乾燥, 跟腱反射延緩", "甲狀腺機能低下 (TSH 偏高、需調藥)"),
        ("怕冷 3 週 + 體重增加", "甲狀腺低下病人 3 週來怕冷加重, 體重增 3kg, 便秘加重, 自行漏服藥物 1 週", "神清, BP 122/78, HR 56, 皮膚乾, 顏面輕度浮腫, 反射稍緩", "甲狀腺機能低下 (劑量不足)"),
        ("便秘 2 週", "甲狀腺低下病人 2 週來便秘加重, 3-4 天一次, 質硬, 否認腹痛血便", "神清, 腹軟, 左下腹可觸及糞塊, 腸鳴音減弱, 無壓痛反跳痛", "甲狀腺機能低下 (合併症)"),
    ],
    "Anxiety Disorder": [
        ("失眠 1 週", "焦慮症病人 1 週來入睡困難, 易醒, 多夢, 否認情緒低落, 工作壓力大", "神清焦慮貌, BP 132/85, HR 90, 心律規則, 神經學檢查正常", "廣泛性焦慮症 (合併失眠)"),
        ("心悸 加重 3 天", "焦慮症病人 3 天來心悸發作頻繁, 持續 5-10 min, 否認胸痛, ECG 既往正常", "神清, BP 128/82, HR 88 規則, 心音清晰, 無雜音, 肺音清, 手指輕度顫抖", "廣泛性焦慮症 (排除心因性後)"),
        ("胸悶 焦慮時", "焦慮症病人近 1 週於壓力情境下出現胸悶+ 過度呼吸, 持續 10-15 min, 否認暈厥", "神清, BP 135/85, HR 95, 心肺正常, 手部輕度顫抖, 神經學檢查正常", "廣泛性焦慮症 (恐慌發作合併)"),
    ],
    "Migraine": [
        ("偏頭痛 3 天 反覆", "偏頭痛病人 3 天來右側顳部搏動性頭痛反覆, 每次 4-6 hr, 怕光怕吵, 否認外傷", "神清, BP 122/78, 頭顱無壓痛, 神經學檢查無局灶徵象, 頸部活動正常", "偏頭痛 (無先兆、急性發作)"),
        ("頭痛 + 怕光怕吵 2 天", "偏頭痛病人 2 天前發作, 左側額顳區搏動性痛, 8/10 分, 噁心 1 次嘔吐, 怕光怕吵", "神清痛苦面容, 頭顱無壓痛, 瞳孔等大反射存, 頸部柔軟無抵抗, 神經學正常", "偏頭痛 (典型發作)"),
        ("頭痛 + 嘔吐 1 天", "急性頭痛病人 1 天前出現劇烈頭痛伴嘔吐 3 次, 否認外傷意識改變, 既往偏頭痛史", "神清, BP 138/86, 頭顱無壓痛, 頸部柔軟, 神經學檢查無局灶徵象, 眼底未見視乳頭水腫", "偏頭痛 (急性、需排除其他)"),
    ],
    "GERD": [
        ("胃酸逆流 1 週", "GERD 病人 1 週來胸骨後燒灼感, 平躺加重, 進食後 30 min 明顯, 否認吞嚥困難", "神清, 上腹輕壓痛, 腸鳴音正常, 無反跳痛, 心肺正常", "胃食道逆流 (持續性)"),
        ("胸悶 餐後加重", "GERD 病人 1 週來餐後胸悶, 平躺加重, 起身可緩解, 否認運動誘發, 既往 PPI 治療", "神清, BP 125/78, 心律規則, 上腹劍突下壓痛 (+), 腸鳴音正常", "胃食道逆流 (典型症狀)"),
        ("咳嗽 餐後 5 天", "GERD 病人 5 天來餐後咳嗽, 平躺加重, 晨起聲音沙啞, 否認上呼吸道感染症狀", "神清, 咽後壁輕度紅, 扁桃腺 (-), 雙肺呼吸音清, 上腹輕壓痛", "胃食道逆流 (LPR 喉咽逆流)"),
    ],
    "BPH": [
        ("夜尿 4-5 次/晚", "BPH 病人 1 個月來夜尿增至 4-5 次, 日間排尿次數正常, 否認排尿痛血尿", "神清, 下腹未觸及膀胱, 直腸指診攝護腺 II 度肥大 質中無結節, 無壓痛", "攝護腺肥大 (LUTS 加重)"),
        ("排尿困難 1 個月", "BPH 病人 1 個月來排尿啟動困難, 尿流變細, 夜尿 3 次, 否認血尿膿尿", "神清, 下腹軟, 攝護腺 II-III 度肥大 質中, 無壓痛, 殘尿感 (+)", "攝護腺肥大 (尿流不暢)"),
        ("尿流變細 2 週", "BPH 病人 2 週來尿流變細, 排尿時間延長, 偶有滴尿, 否認尿失禁", "神清, 攝護腺 II 度肥大 質中, 無結節壓痛, 下腹無膨隆", "攝護腺肥大 (進展中)"),
    ],
    "Heart Failure": [
        ("喘 加重 3 天", "CHF 病人 3 天前喘明顯加重, 平躺加重需端坐, 體重增 3kg, 雙下肢水腫加重", "神清端坐, BP 105/68, HR 102, 頸靜脈怒張, 肺部雙下肺濕囉音, 雙下肢凹陷性水腫 +++", "鬱血性心衰竭 (NYHA III, 急性惡化)"),
        ("下肢水腫 1 週", "CHF 病人 1 週來雙下肢水腫加重, 鞋子穿不下, 體重增 2kg, 喘略加重", "神清, BP 118/72, HR 88, 頸靜脈輕度怒張, 雙肺底少許濕囉音, 雙下肢水腫 ++", "鬱血性心衰竭 (水腫加重)"),
        ("夜間平躺呼吸困難 5 天", "CHF 病人 5 天來夜間平躺即喘, 需墊 2-3 個枕頭, 否認胸痛, 服利尿劑 furosemide 規律", "神清, BP 122/76, HR 90, 頸靜脈怒張, 雙肺底濕囉音, 雙下肢凹陷性水腫", "鬱血性心衰竭 (端坐呼吸)"),
    ],
    "Dementia": [
        ("健忘加重 1 月 (家屬陳述)", "MCI 病人, 家屬訴近 1 月健忘明顯加重, 重複問同樣問題, 否認外傷, 否認情緒低落", "神清定向 (人) 可 (時地) 部分, MMSE 22/30, 神經學檢查無局灶徵象, 步態正常", "輕度認知障礙 (MCI 進展)"),
        ("走錯路 1 次", "MCI 病人 3 天前去常去市場走錯路, 約 1 hr 後自行返家, 否認外傷意識改變", "神清, 定向人時部分, 對近事記憶減退, 神經學正常, 步態穩", "輕度認知障礙 (定向感下降)"),
        ("情緒易怒 2 週", "MCI 病人, 家屬訴近 2 週情緒易怒易煩躁, 對日常事務挫折感大, 睡眠減少", "神清, 對話可配合但煩躁, 定向部分, 神經學檢查無局灶徵象", "輕度認知障礙 (行為症狀)"),
    ],
    "Depression": [
        ("情緒低落 1 個月", "病人 1 個月來情緒低落, 興趣減退, 體重略減, 否認自殺意念, 與家庭衝突相關", "神清表情淡漠, 對話遲緩, 神經學檢查正常, 否認幻聽幻視", "重度憂鬱症 (中度)"),
        ("失眠 2 週 + 食慾減退", "憂鬱症病人 2 週來失眠 (早醒型) + 食慾差, 體重 1 個月減 2kg, 服 SSRI 中", "神清表情低落, BP 118/72, 心肺正常, 神經學正常, BMI 偏低", "重度憂鬱症 (典型症狀)"),
        ("對事物失去興趣", "病人 1 個月來對既往興趣 (運動 / 社交) 失去興趣, 自述疲倦, 否認自殺意念", "神清表情平淡, 對話可配合, 神經學檢查正常", "重度憂鬱症 (Anhedonia)"),
    ],
    "Gout": [
        ("腳趾痛 急性 1 天 紅腫熱", "痛風病人 1 天前夜間突發左足拇趾劇痛, 紅腫熱明顯, 不能著地, 飲酒後發作", "神清, T 37.5, 左足第一蹠趾關節紅腫熱痛 (+++), 不能負重, 全身關節否認受累", "痛風 急性發作 (典型蹠趾關節)"),
        ("膝紅腫熱痛 2 天", "痛風病人 2 天來右膝紅腫熱痛, 不能屈曲, 否認外傷, 既往多次足部痛風發作", "神清, T 37.2, 右膝關節紅腫熱壓痛, ROM 受限, 不能負重, 髕骨浮動試驗 (+)", "痛風 急性發作 (非典型膝關節)"),
        ("腳踝腫痛 半夜醒", "痛風病人半夜被右踝劇痛痛醒, 紅腫不能著地, 否認外傷, 尿酸近期未追蹤", "神清, T 37.0, 右踝關節腫脹紅熱, 壓痛 (++), 主被動 ROM 受限", "痛風 急性發作"),
    ],
    "Osteoporosis": [
        ("腰背痛 加重 2 週", "骨鬆病人 2 週來腰背痛加重, 翻身咳嗽明顯, 否認外傷, 既往 T-score -2.8", "神清, 胸 12/腰 1 棘突壓痛 (+), 叩痛 (+), 神經學檢查無下肢無力感覺異常", "骨質疏鬆症 (壓迫性骨折需排除)"),
        ("輕微跌倒後痛 3 天", "骨鬆病人 3 天前家中跌倒, 臀部著地, 後出現右髖痛, 行走困難, 否認頭部外傷", "神清, BP 130/82, 右髖外旋外展受限, 壓痛 (+), 不能負重, 神經學正常", "骨質疏鬆症 (跌倒後評估)"),
    ],
}

# 健康 / 急性問題 4-tuple pool: (CC, HPI, PE, Dx)
GENERIC_CASES: list[tuple[str, str, str, str]] = [
    # 呼吸道
    ("咳嗽 3 天",
     "病人 3 天前開始咳嗽, 乾咳為主, 無痰, 伴鼻塞流涕, 無發燒, 自服感冒藥未明顯改善, 否認過敏史",
     "神清, T 36.8, 咽部輕度充血, 扁桃腺 (-), 雙肺呼吸音清, 無乾濕囉音",
     "急性上呼吸道感染"),
    ("咳嗽 帶白痰 5 天",
     "病人 5 天前開始咳嗽, 第 2 天起有白痰, 量中等, 否認胸痛喘, 曾低熱 37.6 已退",
     "神清, T 37.0, 咽部充血, 雙肺呼吸音粗, 右下肺聞及少許濕囉音, 心律規則",
     "急性支氣管炎"),
    ("夜咳 1 週",
     "病人前週感冒已痊癒, 但近 1 週夜間 2-3 點咳嗽發作, 無痰, 日間正常, 否認過敏氣喘史",
     "神清, 咽部輕度紅, 雙肺呼吸音清, 偶聞少量乾性囉音, 心律規則",
     "感染後咳嗽 (Post-infectious cough)"),
    ("流鼻水 5 天",
     "病人 5 天前開始流清水樣鼻涕, 鼻塞, 偶有打噴嚏, 無發燒咳嗽, 否認過敏史",
     "神清, T 36.7, 鼻黏膜紅腫, 鼻腔清水樣分泌物, 咽部輕度紅, 肺音清",
     "急性鼻咽炎"),
    ("鼻塞 + 流鼻水 3 天",
     "病人有過敏史, 3 天前接觸冷空氣後鼻塞流清涕, 打噴嚏連續, 無發燒, 既往發作多次",
     "神清, 鼻黏膜蒼白水腫, 鼻甲肥大, 清水樣分泌物, 咽部輕度紅, 雙肺呼吸音清",
     "過敏性鼻炎"),
    ("喉嚨痛 2 天",
     "病人 2 天前開始喉嚨痛, 吞嚥加重, 伴低熱 37.8, 自服 paracetamol 短暫緩解, 否認皮疹",
     "神清, T 37.6, 咽部明顯充血, 扁桃腺 II 度腫大、見白色滲出物, 頸部淋巴結輕度腫大壓痛",
     "急性扁桃腺炎"),
    ("聲音沙啞 4 天",
     "病人 4 天前因感冒後聲音沙啞, 喉嚨乾癢, 否認吞嚥困難, 工作需用嗓多",
     "神清, 咽部輕度充血, 扁桃腺 (-), 喉部間接鏡未做, 雙肺呼吸音清",
     "急性咽喉炎"),
    ("發燒 + 喉嚨痛 2 天",
     "病人 2 天前發燒至 38.5, 伴喉嚨痛吞嚥困難, 否認咳嗽腹瀉皮疹, 同事多人感冒",
     "神清, T 38.3, 咽部充血明顯, 扁桃腺 II 度腫大白色滲出, 頸部 LN 腫大壓痛 (+), 肺音清",
     "急性扁桃腺炎"),
    ("輕度發燒 38.2 一天",
     "病人 1 天前發燒 38.2, 伴全身痠痛疲倦, 否認局部疼痛或感染症狀, 否認旅遊接觸史",
     "神清, T 38.0, 咽部輕度紅, 扁桃腺 (-), 雙肺呼吸音清, 心律規則, 腹軟無壓痛",
     "病毒性發燒症候群"),
    # 腸胃
    ("拉肚子 4 次/日 持續 2 天",
     "病人 2 天前開始水樣腹瀉, 每日 4-5 次, 無黏液血便, 伴輕度腹絞痛, 否認發燒嘔吐, 飲食史可疑路邊攤",
     "神清, T 36.9, BP 118/72, 黏膜稍乾, 腹軟, 臍周輕壓痛 (+), 腸鳴音活躍, 無反跳痛",
     "急性腸胃炎"),
    ("嘔吐 3 次 半天 + 腹痛",
     "病人半天前進食外賣後出現噁心嘔吐 3 次, 伴上腹絞痛, 否認血便, 同行家人有類似症狀",
     "神清痛苦面容, T 37.2, BP 122/78, 上腹壓痛 (+), 無反跳痛, 腸鳴音活躍",
     "病毒性腸胃炎"),
    ("腹痛 + 拉肚子 1 天",
     "病人 1 天前進食隔夜飯後出現腹痛伴腹瀉 5-6 次水樣, 否認黏液血便, 否認發燒嘔吐",
     "神清, T 37.1, 腹軟, 臍周及下腹輕壓痛, 腸鳴音活躍, 無反跳痛, 無肌緊張",
     "急性腸胃炎 (food poisoning 疑似)"),
    ("胃悶 餐後不適 1 週",
     "病人 1 週來餐後 30 min 內出現胸骨後悶熱感, 平躺加重, 否認吞嚥困難或體重減輕",
     "神清, BP 126/78, 上腹劍突下輕壓痛, 無反跳痛, 腸鳴音正常, 心肺正常",
     "胃食道逆流 (新診)"),
    # 皮膚
    ("皮膚紅疹 2 天",
     "病人 2 天前雙前臂出現紅疹搔癢, 接觸新洗衣劑後出現, 否認發燒呼吸困難",
     "神清, T 36.6, 雙前臂屈側紅斑伴丘疹, 邊界清, 無膿皰, 未見全身性皮疹",
     "接觸性皮膚炎"),
    ("搔癢 + 紅疹 1 週",
     "病人 1 週來身上反覆出現風團伴搔癢, 數小時內消退, 否認食物過敏明確誘因",
     "神清, 軀幹及四肢散在風團, 大小不一, 邊界清, 無關節腫脹, 無黏膜受累",
     "蕁麻疹"),
    ("蕁麻疹 反覆 1 週",
     "病人 1 週來蕁麻疹反覆發作, 每日數次, 服 antihistamine 部分緩解, 否認新藥物或食物史",
     "神清, 軀幹散在風團 + 紅斑, 雙手背為甚, 無黏膜水腫, 心肺正常",
     "慢性蕁麻疹 (待查過敏原)"),
    # 神經 / 肌肉骨骼
    ("頭痛 2 天",
     "病人 2 天來雙顳區壓迫感頭痛, 緊張時加重, 否認怕光怕吵或噁心嘔吐, 工作壓力大",
     "神清, BP 128/82, 頭顱無壓痛, 頸部肌肉緊張壓痛 (+), 神經學檢查無局灶徵象",
     "緊張型頭痛"),
    ("頭暈 3 天",
     "病人 3 天前晨起翻身時突發旋轉性頭暈, 持續 30 sec 緩解, 反覆發作, 否認耳鳴聽力改變",
     "神清, BP 122/76, Dix-Hallpike 試驗 (+) 右側, 神經學檢查正常, 心律規則",
     "前庭功能失調 (BPPV 需排除)"),
    ("偏頭痛 1 天",
     "病人 1 天前發作右側顳區搏動性頭痛, 8/10 分, 怕光怕吵, 既往類似發作多次",
     "神清痛苦面容, BP 130/82, 頭顱無壓痛, 神經學檢查無局灶徵象, 頸部柔軟",
     "偏頭痛 (急性發作)"),
    ("腰痛 3 天 搬重物後",
     "病人 3 天前搬重物後出現下背疼痛, 彎腰加重, 否認下肢放射痛或麻木無力",
     "神清, 腰部肌肉緊張壓痛 (L4-L5 旁), SLR (-), 下肢肌力對稱 5/5, 感覺正常",
     "急性下背痛 (肌肉拉傷)"),
    ("膝痛 + 腫脹 2 天",
     "病人 2 天前運動後右膝疼痛腫脹, 不能完全屈曲, 否認外傷史明確或彈響",
     "神清, 右膝關節輕度腫脹, 內側關節線壓痛 (+), McMurray (-), ROM 受限, 無發熱",
     "膝關節扭傷"),
    ("肩頸僵硬 1 週",
     "病人 1 週來肩頸僵硬伴後腦脹痛, 工作久坐電腦, 否認上肢麻木",
     "神清, 頸部活動受限尤旋轉, 肌肉緊張壓痛 (+), 神經學檢查無局灶徵象",
     "頸椎症候群 / 緊張型頭痛"),
    # 五官
    ("耳痛 2 天",
     "病人 2 天前左耳痛, 游泳後出現, 伴輕度聽力下降, 否認發燒分泌物",
     "神清, T 36.8, 左外耳道輕度紅腫, 鼓膜可見正常, 牽拉耳廓痛 (+)",
     "急性外耳炎"),
    ("眼睛紅 + 分泌物 3 天",
     "病人 3 天前雙眼開始紅 + 黃色分泌物, 晨起黏住睫毛, 否認視力減退或外傷",
     "神清, 雙眼結膜充血明顯, 分泌物 (黃色) 多, 角膜清, 瞳孔等大反射存",
     "急性結膜炎"),
    # 其他
    ("失眠 1 週",
     "病人 1 週來入睡困難, 易醒多夢, 否認情緒低落, 工作壓力大",
     "神清, BP 122/78, 心肺正常, 神經學檢查正常, 否認自殺意念",
     "失眠症 (壓力相關)"),
    ("疲倦 2 週",
     "病人 2 週來持續疲倦, 睡眠 7-8 hr 仍累, 體重未變, 否認情緒低落或運動",
     "神清, BP 118/72, 結膜無蒼白, 甲狀腺未觸及腫大, 心肺正常",
     "慢性疲倦 (待查、需 CBC + TSH)"),
]


# ─────────────────────────────────────────────────────────
# Vital signs profile (chronic-aware ranges)
# ─────────────────────────────────────────────────────────

def gen_vital_signs(chronic_set: set[str], age: int, rng: random.Random) -> dict[str, Any]:
    """根據 chronic 跟年齡生 vital signs。"""
    # BP base
    if "Hypertension" in chronic_set:
        sbp = rng.randint(140, 168)
        dbp = rng.randint(86, 102)
    elif "Heart Failure" in chronic_set:
        sbp = rng.randint(95, 125)
        dbp = rng.randint(60, 80)
    elif age >= 70:
        sbp = rng.randint(125, 145)
        dbp = rng.randint(72, 88)
    else:
        sbp = rng.randint(108, 130)
        dbp = rng.randint(65, 82)

    # HR
    if "Atrial Fibrillation" in chronic_set:
        hr = rng.randint(70, 110)
    elif "Heart Failure" in chronic_set:
        hr = rng.randint(85, 105)
    else:
        hr = rng.randint(62, 90)

    # T
    t = round(rng.uniform(36.4, 37.4), 1)

    # SpO2
    if "COPD" in chronic_set:
        spo2 = rng.randint(91, 96)
    elif "Asthma" in chronic_set:
        spo2 = rng.randint(94, 99)
    else:
        spo2 = rng.randint(97, 100)

    return {
        "blood_pressure_systolic": sbp,
        "blood_pressure_diastolic": dbp,
        "heart_rate": hr,
        "respiratory_rate": rng.randint(14, 20),
        "temperature_c": t,
        "oxygen_saturation": spo2,
    }


# ─────────────────────────────────────────────────────────
# Lab results (disease-specific)
# ─────────────────────────────────────────────────────────

def gen_lab_results(chronic_set: set[str], rng: random.Random) -> list[dict[str, Any]]:
    """根據 chronic 隨機生 1-4 個 lab result。"""
    labs: list[dict[str, Any]] = []

    if "Type 2 Diabetes" in chronic_set:
        hba1c = round(rng.uniform(6.5, 9.2), 1)
        labs.append({
            "name": "HbA1c",
            "value": hba1c,
            "unit": "%",
            "reference_range": "<6.0",
            "is_abnormal": hba1c >= 6.5,
        })
        glu = rng.randint(110, 220)
        labs.append({
            "name": "Fasting Glucose",
            "value": glu,
            "unit": "mg/dL",
            "reference_range": "70-99",
            "is_abnormal": glu > 99,
        })

    if "Hyperlipidemia" in chronic_set:
        ldl = rng.randint(95, 180)
        labs.append({
            "name": "LDL",
            "value": ldl,
            "unit": "mg/dL",
            "reference_range": "<100",
            "is_abnormal": ldl >= 100,
        })

    if "CKD Stage 3" in chronic_set:
        cr = round(rng.uniform(1.4, 2.2), 2)
        labs.append({
            "name": "Creatinine",
            "value": cr,
            "unit": "mg/dL",
            "reference_range": "0.7-1.3",
            "is_abnormal": True,
        })

    if "Hypothyroidism" in chronic_set:
        tsh = round(rng.uniform(2.8, 7.5), 2)
        labs.append({
            "name": "TSH",
            "value": tsh,
            "unit": "uIU/mL",
            "reference_range": "0.4-4.5",
            "is_abnormal": tsh > 4.5,
        })

    if "Gout" in chronic_set:
        uric = round(rng.uniform(6.5, 11.0), 1)
        labs.append({
            "name": "Uric Acid",
            "value": uric,
            "unit": "mg/dL",
            "reference_range": "<7.0",
            "is_abnormal": uric > 7.0,
        })

    if "Asthma" in chronic_set or "COPD" in chronic_set:
        # generic CBC
        wbc = round(rng.uniform(5.0, 13.0), 1)
        labs.append({
            "name": "WBC",
            "value": wbc,
            "unit": "10^3/uL",
            "reference_range": "4.0-10.0",
            "is_abnormal": wbc > 10.0,
        })

    # 健康人 / 沒 chronic 也偶爾有 CBC
    if not labs and rng.random() < 0.4:
        wbc = round(rng.uniform(5.0, 9.5), 1)
        labs.append({
            "name": "WBC",
            "value": wbc,
            "unit": "10^3/uL",
            "reference_range": "4.0-10.0",
            "is_abnormal": False,
        })
        hgb = round(rng.uniform(12.0, 15.5), 1)
        labs.append({
            "name": "Hemoglobin",
            "value": hgb,
            "unit": "g/dL",
            "reference_range": "12.0-16.0",
            "is_abnormal": False,
        })

    return labs


# ─────────────────────────────────────────────────────────
# Free-text findings (xray / ecg) -- 少數 visit 才生
# ─────────────────────────────────────────────────────────

XRAY_FINDINGS_POOL = [
    "Bilateral lung fields clear. No consolidation.",
    "右下肺輕度 infiltrate, suggest follow-up.",
    "Mild cardiomegaly noted. CT ratio ~0.52.",
    "雙肺紋理增加, no acute findings.",
    "Normal chest X-ray.",
]

ECG_FINDINGS_POOL = [
    "NSR, rate 78, no acute ST changes.",
    "Atrial fibrillation, controlled rate ~92.",
    "Sinus tachycardia, rate 105.",
    "NSR with LVH pattern.",
    "ECG within normal limits.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = os.environ.get("ENVIRONMENT", "").lower()
    if env != "dev":
        log.error("ENVIRONMENT=dev required")
        return 1

    rng = random.Random(SEED)
    db: Session = SessionLocal()
    try:
        # 第一間 clinic + owner
        clinic = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
        if not clinic:
            log.error("沒 clinic, 先跑 scripts/seed")
            return 1

        owner = db.scalars(
            select(User).order_by(User.created_at).limit(1)
        ).first()
        if not owner:
            log.error("沒 user")
            return 1

        # idempotent: 先刪 extended_mock 的 visit + examination
        if not args.dry_run:
            n_exam = db.execute(
                delete(VisitExamination).where(
                    VisitExamination.clinic_id == clinic.id,
                    VisitExamination.source == SOURCE_TAG,
                )
            ).rowcount
            n_visit = db.execute(
                delete(Visit).where(
                    Visit.clinic_id == clinic.id,
                    Visit.source == SOURCE_TAG,
                )
            ).rowcount
            log.info("先刪舊 extended: %d visits + %d examinations", n_visit, n_exam)

        # 拿所有 patient + 對應 chronic
        patients = db.scalars(
            select(Patient).where(
                Patient.clinic_id == clinic.id,
                Patient.is_demo_data.is_(True),
            )
        ).all()
        log.info("處理 %d patient", len(patients))

        chronics_by_pid: dict[UUID, set[str]] = {}
        for prob in db.scalars(
            select(PatientProblem).where(PatientProblem.clinic_id == clinic.id)
        ).all():
            chronics_by_pid.setdefault(prob.patient_id, set()).add(prob.problem_name)

        now = datetime(2026, 6, 27, tzinfo=timezone.utc)
        n_visit_added = 0
        n_exam_added = 0

        for p in patients:
            chronic_set = chronics_by_pid.get(p.id, set())
            # 計算年齡
            if p.date_of_birth:
                age = now.year - p.date_of_birth.year
            else:
                age = 50

            # visit 數 weighted by chronic count
            if len(chronic_set) >= 2:
                n_visits = rng.choice([2, 3, 3])
            elif len(chronic_set) == 1:
                n_visits = rng.choice([1, 2, 3])
            else:
                n_visits = rng.choice([1, 1, 2])

            # 生 visits (時間從舊到新分散在過去 1-18 個月)
            time_slots = sorted(
                rng.sample(range(1, 540), n_visits),  # 540 天 ≈ 18 個月
                reverse=True,  # 最舊在前
            )

            for slot_days in time_slots:
                visit_date = now - timedelta(days=slot_days)

                # 4-tuple: chief_complaint, hpi, physical_exam, diagnosis (一起抽保證對齊)
                # chronic patient: 70% 看 chronic 相關、30% 也來看急性問題 (高血壓也會感冒)
                if chronic_set and rng.random() < 0.7:
                    pick_chronic = rng.choice(list(chronic_set))
                    cases = CHRONIC_CASES.get(pick_chronic, GENERIC_CASES)
                    cc, hpi, pe, dx = rng.choice(cases)
                else:
                    cc, hpi, pe, dx = rng.choice(GENERIC_CASES)

                visit_uuid = uuid4()
                visit = Visit(
                    id=visit_uuid,
                    clinic_id=clinic.id,
                    patient_id=p.id,
                    doctor_user_id=owner.id,
                    visit_date=visit_date,
                    chief_complaint=cc,
                    hpi=hpi,
                    physical_exam=pe,
                    diagnosis=dx,
                    status="completed",
                    source=SOURCE_TAG,
                    is_demo_data=True,
                )
                db.add(visit)
                n_visit_added += 1

                # examination
                vital = gen_vital_signs(chronic_set, age, rng)
                labs = gen_lab_results(chronic_set, rng)
                xray = rng.choice(XRAY_FINDINGS_POOL) if rng.random() < 0.15 else None
                ecg = rng.choice(ECG_FINDINGS_POOL) if "Atrial Fibrillation" in chronic_set or rng.random() < 0.08 else None

                exam = VisitExamination(
                    id=uuid4(),
                    clinic_id=clinic.id,
                    visit_id=visit_uuid,
                    patient_id=p.id,
                    vital_signs_json=vital,
                    lab_results_json=labs if labs else None,
                    xray_findings=xray,
                    ecg_findings=ecg,
                    free_notes=None,
                    source=SOURCE_TAG,
                    is_demo_data=True,
                )
                db.add(exam)
                n_exam_added += 1

        # 順手補 jimmy 5 個既有 visit 的 examination (它們的 source='mock' 不在我刪除範圍)
        # 這樣 demo 點 jimmy 病人也看得到 vital signs
        jimmy_visits_no_exam = db.scalars(
            select(Visit)
            .outerjoin(
                VisitExamination,
                VisitExamination.visit_id == Visit.id,
            )
            .where(
                Visit.clinic_id == clinic.id,
                Visit.source == "mock",
                VisitExamination.id.is_(None),
            )
        ).all()
        n_jimmy_exam = 0
        for v in jimmy_visits_no_exam:
            chronic_set = chronics_by_pid.get(v.patient_id, set())
            p = db.get(Patient, v.patient_id)
            age = (now.year - p.date_of_birth.year) if (p and p.date_of_birth) else 50
            vital = gen_vital_signs(chronic_set, age, rng)
            labs = gen_lab_results(chronic_set, rng)
            exam = VisitExamination(
                id=uuid4(),
                clinic_id=clinic.id,
                visit_id=v.id,
                patient_id=v.patient_id,
                vital_signs_json=vital,
                lab_results_json=labs if labs else None,
                xray_findings=None,
                ecg_findings=None,
                free_notes=None,
                source=SOURCE_TAG,
                is_demo_data=True,
            )
            db.add(exam)
            n_jimmy_exam += 1
            n_exam_added += 1

        if args.dry_run:
            db.rollback()
            log.info("[DRY RUN] 不寫 DB, 預計 +%d visits +%d examinations (jimmy 補 +%d)",
                     n_visit_added, n_exam_added, n_jimmy_exam)
        else:
            db.commit()
            log.info("=" * 60)
            log.info("Extend visits + examinations 完成")
            log.info("  visits             + %d", n_visit_added)
            log.info("  visit_examinations + %d (其中 jimmy 補 %d)", n_exam_added, n_jimmy_exam)
            log.info("=" * 60)
        return 0
    except Exception:
        db.rollback()
        log.exception("extend_visits 失敗, rollback")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
