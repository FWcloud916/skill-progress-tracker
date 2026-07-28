# skill-progress-tracker 改善計劃

> **依據:** 對照 `mattpocock/skills` 的 `writing-great-skills` 原則,逐行審視現行 `skills/progress-tracker/SKILL.md`(309 行)後制定。
> **核心目標:** 降低 context load、消除 duplication、用 leading words 強化行為錨定 — 全程以既有 evals(trigger matrix + scenarios)當回歸安全網。
> **建立日期:** 2026-07-27

---

## Phase 1 — Pruning pass(優先度:最高)

### 1a. Migration 段落 progressive disclosure

**問題:** SKILL.md 309 行中 migration 佔約 120 行,但 migration 是只有單一 branch 會走到的路徑;大多數 session 只做 create / update / close。依 branch 判準(所有分支都需要的留頂層,只有部分分支會走到的推下去),這 120 行不該常駐頂層。

**做法:**

1. SKILL.md 只保留:
   - Preflight 偵測規則(每次 create 都要跑,屬於全分支內容)
   - `MIGRATION_GATE_START/END` 硬約束區塊(verify.sh 已鏡射,維持 single source of truth 機制)
   - 一行 context pointer
2. 以下整段搬到新檔 `references/migration.md`:
   - 七步 migration 流程細節(步驟 3–7 的展開內容)
   - 五種 `Kind` 值語義與 disposition 規則
   - v1 → v2 record 升級行為
   - Migration command reference 區塊
3. **Pointer 措辭用命令式**,決定觸發率的是措辭不是目標:
   - ✅ `A migration was approved → read references/migration.md in full before running any migration command.`
   - ❌ `See references/migration.md for details.`

### 1b. 消除 migration 指令的 duplication

**問題:** migration 指令目前出現兩次 — 編號步驟內一次、「Migration command reference」區塊一次。Duplication 除了維護成本,還會虛增該內容在 information hierarchy 上的地位。

**做法:** 權威版本留在 `references/migration.md` 的 command reference,步驟內文改為指向。

### 1c. 逐句 no-op 測試

**規則:** 對每一句問「這句有沒有改變相對於模型預設的行為?」失敗的**整句刪除**,不修剪字詞。

**已識別候選:**

- `Use --dry-run first to preview what would be created.` — flag 說明已含 preview 語意,近乎 no-op
- 各處「brief notes」「as needed」等修飾語逐一檢驗

**驗收:** 拆分 + 修剪後 SKILL.md 目標 ≤ 180 行,`bash scripts/verify.sh` 通過,evals 全綠。

---

## Phase 2 — Description 重寫 + invocation 語意

### 2a. Description 依「one trigger per branch」重寫

現行 description 的 trigger 條列品質不錯(含 negative trigger),但仍可依三規則收緊:

1. **Front-load leading word** — 第一個詞就做觸發工作
2. **每個 branch 只留一個 trigger** — create / update / audit / close-out / migrate 各一,同義改寫視為 duplication 合併
3. **刪掉 body 已有的 identity 描述**

Description 每一輪都躺在 context window 裡,是全 repo 最貴的文字。

### 2b. Invocation 語意決策(記錄進 design-decisions.md)

- `check`(audit):保留 model-invoked — 期望 agent 在 close-out 前自動跑
- Migration:1a 拆出後天然降級為「僅由主 skill 指路才載入」的層級,等效降低 context load,**不另拆成獨立 skill**(granularity 經濟學:每次 split 都花掉一種 load,目前拆不出對應價值)
- Router skill:目前僅兩個 skill,不需要

**驗收:** trigger-matrix.json 全數通過(description 改動直接影響觸發,這是它的安全網)。

---

## Phase 3 — Leading words 重構

### 3a. Migration → **two-phase commit**

inventory → audit(= prepare)→ finalize(= commit)→ confirm-deleted 的結構天生就是 2PC。在 SKILL.md gate 區塊與 `references/migration.md` 開頭各錨定一次:

> Migration is a two-phase commit: the audit is the prepare phase; nothing is deleted until it votes yes.

徵召模型既有的 2PC 先驗 — 其語意模型中不存在「跳過 prepare 直接 commit」的路徑,比條列 MUST NOT 更穩。

### 3b. 強化既有 leading words

- **preflight** — 已是好詞,擴大到 description 也使用,讓觸發與執行共用同一錨點
- Status lifecycle 的 `blocked ↕` 圖已足夠緊湊,維持

### 3c. Negation 掃描

保留正當的 hard guardrail(「Never delete current tracker items automatically」屬此類,保留並已配對正向指示)。其餘 do not / never 逐一檢查能否改寫為正向陳述目標行為。

---

## Phase 4 — 功能性移植(挑選執行)

1. **`CONTEXT.md`(共享語言)** — 集中定義 domain 詞彙:scope、disposition、Kind、tracker-dir、preflight、two-phase commit。AGENTS.md 與 SKILL.md 引用之,減少各處重複解釋。
2. **Failure-mode review checklist** — 把六個 failure mode(premature completion / duplication / sediment / sprawl / no-op / negation)做成人工 checklist,納入 verify.sh 流程說明;之後每次改 SKILL.md 都過一遍。
3. **Tautological eval 自查** — 檢查 grader 是否用與 skill 相同的邏輯判分;期望值必須來自獨立 truth source。

---

## 執行順序與驗收總表

| 順序 | 項目 | 產出 | 驗收 |
|---|---|---|---|
| 1 | 1a + 1b Migration 拆分 | `references/migration.md` + 縮短的 SKILL.md | verify.sh + evals 全綠 |
| 2 | 1c No-op 修剪 | SKILL.md ≤ 180 行 | 同上 |
| 3 | 2a Description 重寫 | 新 description | trigger matrix 全過 |
| 4 | 2b Invocation 決策 | design-decisions.md 新條目 | — |
| 5 | 3a–3c Leading words | 修訂後全文 | scenarios 全綠 |
| 6 | Phase 4 擇項 | CONTEXT.md 等 | verify.sh 通過 |

**每個 phase 是一個獨立 commit / PR,eval 全綠才進下一個。**

---

## 執行偏差記錄(2026-07-28,PR #1 review 後補記)

1. **基線行數 309 → 302:** 本計劃撰寫時(2026-07-27)量測 SKILL.md 為 309 行;
   執行開始時(2026-07-28)main 上的 SKILL.md 為 302 行(期間 main 有其他變更落地)。
   驗收指標「≤ 180 行」以執行起點 302 為基線計算,PROGRESS.md 記錄的 302 為準。
2. **Phase 4 第 1 項改道:** 計劃寫 `CONTEXT.md`,實作裁決為
   `docs/domain-models.md` §0 Shared Vocabulary — 詞彙緊鄰其實體定義、
   AGENTS.md 的 task→doc 表已路由到該檔;獨立的 repo-root 檔案會把命名與
   agents 實際閱讀的 domain 參考拆成兩處。完整理由見
   `docs/design-decisions.md`「Shared vocabulary lives in domain-models.md」條目。
