# #8 測試環境交接與重跑流程

這份文件交付測試準備；目前沒有授權 Linux 主機、Claude 憑證配置位置或 E01–E10 的實測證據。#8 保持 open，#10/#11 等人工審查確認 go 後才開始。命名與網域不影響這次測試。

## 先交接什麼

以下資料填在團隊私密的交接記錄，公開 PR 只放不敏感的參照 ID。任何空白都不能用現有 SSH config／雲端帳戶猜補。

| 資料 | 操作者需要知道的內容 |
|---|---|
| 主機與授權 | 測試機 alias、Linux 版本／架構、誰授權使用、誰維護；是否專供 disposable 測試 |
| Docker／runsc | 本機 Unix socket、Docker 與 runsc 固定版本、runsc binary checksum、註冊的 runtime 實際 executable／flags；PATH 下版本不能代替 daemon 配置核對 |
| 安裝變更 | 缺軟體時由維護者安排安裝及 daemon 重啟窗口；共享主機不能直接重啟 |
| 診斷 image | 已審查 Dockerfile／安裝來源、固定版本清單、repo digest 或本機 image ID；不以 latest 代替。shell/git/Node/npm/Claude/tmux/python3 必須存在 |
| 憑證與預算 | 專用 API workspace、花費上限／停止門檻、負責人、短期注入方式及配置位置參照；不在報告填 key |
| 主機及測試額度 | 可用 CPU/RAM/disk、保留 headroom、各測試限額、CPU 測量容差、測試 timeout、主機告警門檻 |
| 測試資料 | 固定公開 repo commit、package-lock、允許的對外目的地；不帶正式資料 |
| 清理與回報 | 執行人、資源 manifest 位置、清理責任人、遮蔽後證據保存位置 |

image 只是 #8 診斷用，不在此定案 #10 的正式工作映像。實測報告應記錄可重建診斷 image 的 source commit 與版本，而非只留下主機上臨時 tag。若這份材料還不存在，先由操作者補齊再跑。

## 一次測試一份證據包

Python 3.10+，不需額外套件。以下前兩步可以在本機完成；不安裝 runtime、不讀取秘密、不建立容器。使用專案外的私密目錄保存草稿，避免原始 log 意外進 Git。

```sh
SPIKE_EVIDENCE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gvisor-evidence.XXXXXX")"
python3 scripts/gvisor-report.py --init "$SPIKE_EVIDENCE_DIR/report.json"
python3 scripts/gvisor-report.py --check "$SPIKE_EVIDENCE_DIR/report.json"
# 預期 exit 2 / incomplete；十列都是 not_run，不代表測試失敗。
```

在已授權 Linux 主機上先跑既有預檢。下列變數由交接記錄提供；明確指定本機 socket 與 immutable image pin：

```sh
: "${SPIKE_DOCKER_SOCKET:?set authorized local unix socket}"
: "${SPIKE_IMAGE:?set reviewed image digest or image ID}"
python3 scripts/gvisor-preflight.py \
  --docker-socket "$SPIKE_DOCKER_SOCKET" --image "$SPIKE_IMAGE" \
  > "$SPIKE_EVIDENCE_DIR/preflight.json"
```

先檢查 exit code 與報告；只有 `ready_for_manual_matrix_not_go` 才繼續。把實際版本填入 report.environment，preflight.verdict 複製實際值並附該檔案 hash。預檢失敗保留報告及 blocker，不跳過、不補假 pass。

依 [E01–E10 矩陣](gvisor-spike.md#最小矩陣) 逐項執行。每列填實際 command、帶時區起迄時間、exit code、expected/observed、Claude 測試前後版本。CPU／memory／PID 要包含限額與量測，不能只寫「成功」。E06 應保留非 root ptmx、resize、Ctrl-C、斷線重連四項證據；E10 需檔案 hash、session 恢復及缺 key 情境。

report.environment 的 limits_and_headroom、model_budget、credential_delivery_ref 填核對過的數值摘要／私密記錄參照，不填實際秘密。啟動前設定 `DISABLE_AUTOUPDATER=1`，每列前後仍核對版本；變更 image/runtime/Claude 後開新 run，不混成同一環境的結果。

## PTY 重現必須選對 runtime

原矩陣的簡寫省略 `--runtime`，可能誤跑預設 runc。以下僅為 **已授權 Linux 操作者** 的 E06 子測試，資源額度先填交接記錄；這些步驟尚未在本 PR 執行。

```sh
: "${SPIKE_RUN_ID:?use report.run_id}"
: "${SPIKE_CPU_LIMIT:?set test quota}"
: "${SPIKE_MEMORY_LIMIT:?set test memory limit with headroom}"
: "${SPIKE_PID_LIMIT:?set test PID limit}"
SPIKE_PTY_NAME="spike-$SPIKE_RUN_ID-ptmx"
# 清除可能覆蓋 socket 的 Docker client 環境，禁止自動 pull。
env -u DOCKER_CONTEXT -u DOCKER_HOST -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  timeout 30s docker --host "$SPIKE_DOCKER_SOCKET" run \
  --name "$SPIKE_PTY_NAME" --label "sandbox.spike=$SPIKE_RUN_ID" \
  --runtime=runsc --pull=never --network=none --user 1000:1000 \
  --cpus "$SPIKE_CPU_LIMIT" --memory "$SPIKE_MEMORY_LIMIT" \
  --memory-swap "$SPIKE_MEMORY_LIMIT" --pids-limit "$SPIKE_PID_LIMIT" \
  --cap-drop ALL --security-opt no-new-privileges --entrypoint /bin/sh \
  "$SPIKE_IMAGE" -c 'id; exec 3<>/dev/ptmx'
```

先把預定 name/label 記入 manifest。保留 exit code；exit 124 是 timeout，Docker client 結束不代表容器已停止。用同一明確 socket 查本次 name 的 ID、label、Runtime 與 State，記錄後只針對該 ID 清理；停止／刪除前核對 label。若同名已存在則中止並核對舊 manifest，不刪掉重來。不要輸出完整 inspect（可能包含環境秘密）。

參照 [官方 runtime 選擇方式](https://gvisor.dev/docs/user_guide/quick_start/docker/) 與 [上游 #14761](https://github.com/google/gvisor/issues/14761)。上游狀態不能取代固定版本實測；失敗不能以 root 或改成 runc 當通過。

## 檔案格式與審查

每個 evidence 欄位為 `[{"path":"E06-ptmx.log","sha256":"64 位小寫 hex"}]`，相對 report.json 所在資料夾。先遮蔽秘密、保留原本 exit code／量測，再用 `sha256sum`（Linux）或 `shasum -a 256`（macOS）算摘要。檔案更新後要重新計算；原始秘密不可推上 PR。工具只檢查完整性，不會自動偵測或清除秘密。

清理完成，cleanup.status 填 verified，附 manifest、已核對 ID／label 及資源移除證據。未確認清理就保留 not_run，尤其 timeout／中斷時不要自行填成功。

```sh
python3 scripts/gvisor-report.py --check "$SPIKE_EVIDENCE_DIR/report.json"
```

| exit code／結果 | 意義 |
|---|---|
| 2 / incomplete | 必填資料、已執行列、版本、檔案或 hash 等仍有缺失；可包含真實失敗，但還不能完整審查 |
| 1 / failures_recorded | 證據格式完整，至少一列 fail；提交分析與重現，不可 go |
| 0 / ready_for_review | 十列均記 pass 且材料完整；**只代表可人工審查，runtime_go 永遠為 false** |

檢查器不解讀 shell 命令／log、不能證明 log 真實，也不驗證效能容差或隔離安全。OOM 測試可能以非零 exit code 正確通過，因此不是「所有 exit code=0 才 pass」。人工審查者必須核對每列實際符合矩陣，記錄 go/no-go、姓名、環境與證據連結。只有第二份實測 PR 經審查確認 go 才關 #8、解除 #10/#11 的等待；本準備 PR 只能用 Refs #8。
