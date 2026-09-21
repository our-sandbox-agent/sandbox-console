# Runner 與 CLI 語言決策

狀態：**Accepted**（2026-09-21，創辦人決定）。決定：Runner 與 CLI 從第一版採用 Go，控制平面維持 TypeScript，前端維持 JavaScript；不安排任何語言改寫。追蹤 [#7](https://github.com/our-sandbox-agent/sandbox-console/issues/7)；本文件不代表 Runner 已開工。

## 決定配置

| 元件 | 決定 | 取捨 |
|---|---|---|
| 現有前端 | 維持 JavaScript | 不為語言統一而重寫已可用的原型。 |
| 控制平面 | TypeScript；沿用 Hono／Postgres 方向 | 與前端共享資料契約較方便，但仍需要執行期驗證、授權與持久化設計。 |
| Runner | Go，第一版即採用 | 以維護能力、部署及系統整合為理由；Firecracker SDK 的功能覆蓋須驗證，可能仍需直接呼叫 HTTP API，不能當選 Go 的主要理由。不預排重寫。 |
| CLI | Go 編譯執行檔 | 可按目標 OS／架構發布執行檔；靜態連結、終端行為與安裝更新仍須實測。 |

團隊已確認有人維護 Go，因此不採 TypeScript Runner 的替代路線。以下保留當時比較過的 CLI 發布方案作為紀錄；本專案選第一列。

| CLI 發布方案 | 支援狀態與適用情境 | 本專案尚需驗收 |
|---|---|---|
| Go 編譯執行檔 | 既有工具鏈；需有 Go 維護者 | raw terminal、訊號、resize、斷線重連及各平台安裝。 |
| TypeScript + Bun／Deno compile | 兩者均提供正式文件化的單檔及跨平台編譯功能；全 TypeScript 可優先試 Bun，Deno 為替代 | 套件／原生依賴相容性、TTY、憑證儲存、簽章、更新與產物大小。可編譯不等於已通過產品驗收。 |
| TypeScript 編譯 JavaScript，以 npm 發布 | Node 生態既有發布方式；使用者需有支援版本的 Node | 安裝前提、版本檢查與更新流程；不符合「無需預裝 runtime」體驗。 |

[Bun compile](https://bun.sh/docs/bundler/executables) 與 [Deno compile](https://docs.deno.com/runtime/reference/cli/compile/) 的官方文件目前都列出 Linux／macOS／Windows 的 x64 與 arm64 目標；首版支援範圍仍依 #14 驗收，不因編譯器支援而擴大平台承諾。[Node SEA](https://nodejs.org/api/single-executable-applications.html) 目前標示 Stability 1.1／Active development，先不作首版預設，亦不把它與一般 npm 發布混為一談。

## 哪些判斷有依據

- gVisor 可透過 [Docker runtime](https://gvisor.dev/docs/user_guide/quick_start/docker/) 或 [OCI runtime](https://gvisor.dev/docs/user_guide/quick_start/oci/) 介面操作，上層 Runner 不必與底層使用相同語言。
- 程式化依據是 [Docker Engine API](https://docs.docker.com/reference/api/engine/version/v1.45/) 建立容器的 `HostConfig.Runtime` 欄位（例如 `runsc`）；不是從快速入門文件直接推導語言要求。
- Firecracker 的 [Go SDK](https://github.com/firecracker-microvm/firecracker-go-sdk) 封裝其 API，README 也明確指出部分功能尚未涵蓋；[官方入門文件](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md) 展示 API 操作，因此 TypeScript 呼叫 API 也是可行路徑。
- 2026-09-21 查核：[SDK 最新正式 release](https://github.com/firecracker-microvm/firecracker-go-sdk/releases) 仍為 2022-09-07 的 v1.0.0，[Firecracker 最新 release](https://github.com/firecracker-microvm/firecracker/releases) 為 v1.17.0。release 日期不代表主分支停止開發，但不能假設 SDK 跟齊上游；採用前逐項比對所選版本的 API schema 與測試。SDK 覆蓋缺口不會自動否定 Go，也不保證 TypeScript 工期較短。
- Go 能降低部分介接成本是工程判斷，不是安全性或進度保證。是否可複用其他專案程式碼，還要檢查授權、架構耦合、版本與維護成本；不以「同語言」推導「可直接搬用」。
- SDK 主分支的 [內建 API schema](https://github.com/firecracker-microvm/firecracker-go-sdk/blob/main/client/swagger.yaml) 標示 1.4.1；這是規格版本，不應與 SDK 自身 release 版本混用。
- Rust 不是唯一替代方案；目前不引入更多語言，是為了控制團隊維護成本。
- 「Go 起步多 3–4 天」「TypeScript 每階段多一週」尚無本專案實測，不能當排程承諾。

## 對原計劃的修訂（已於本次同步）

原詳細版第 1 步的 Node／Fastify／dockerode 暫時 Runner，以及第 3 步的 Go 重寫，已撤換：第 1 步直接以 Go 實作 Runner，第 3 步第 0 項改為接線與契約測試。已同步的內容：

1. 第 1 步 Runner 語言、套件、adapter 目錄與部署方式。
2. 第 3 步第 0 項改為接入既有 Runner；移除「先 Node 頂著、之後再改寫」退路。
3. 第 3 步套件表、風險與估時，改以接線／契約測試實際範圍估算，不直接扣除一週。
4. 第 4–8 步的 Go 程式例子、Firecracker SDK 與 CLI 發佈方式，依最終配置保持一致。
5. 估時：第 3 步維持 5 週，原本預留給改寫的 5 天改為接線、契約測試與 CLI 邊角緩衝，不直接扣除。

## 下一個可驗收切片

語言定案並完成 #7 必要契約後，由 #8 驗證既有 Linux 測試環境中的 gVisor 相容性。後續才進 Runner 建立／查詢／停止與檔案持久化；不先承諾暖恢復、不因選 Go 就啟用 Firecracker 或購買主機。

Runner 使用固定 adapter 邊界、明確 timeout／錯誤／清理規則與共用契約測試。CLI 和 Runner 可共用資料型別，但 CLI 仍經控制平面操作，不繞過授權邊界。

已確認：團隊有人負責維護 Go，Runner 與 CLI 從第一版採用 Go。其餘不因語言選擇而自動定案的產品契約，仍由 #7 追蹤。
