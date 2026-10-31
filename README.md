# FT9201 on Jetson Nano 2GB

FocalTech FT9201 USB 指紋模組（`2808:93a9`）在 Jetson Nano 上的實驗性移植。

**目前不能用於登入或其他身分驗證。異指測試出現誤判，原因尚未解決。**

## 目前成果

實機環境為 Ubuntu 18.04、ARM64、Linux `4.9.337-tegra`。

- ARM64 原生程式可初始化感測器並擷取 96×96 指紋影像。
- x86-64 廠商比對引擎可透過 QEMU 執行，並建立指紋範本。
- 同指測試：3 次中 2 次匹配；異指測試：3 次全部誤判匹配。
- 公開介面與底層演算法的匹配結果一致；調查尚未找到根本原因。
- 這些少量測試不能用來估計正式辨識率，但已足以否定目前版本作為登入驗證的用途。

沒有提供 PAM 安裝、自動登入或停用密碼功能。範例的離線影像重測不是即時身分驗證。

## 建置

在 Jetson 主機準備依賴：

```bash
sudo apt install build-essential libusb-1.0-0-dev python3 curl binutils
bash build.sh --native-only
```

檢查 USB 存取，並下載、擷取感測器韌體：

```bash
sudo ./probe
bash prepare-firmware.sh
```

擷取一張影像：

```bash
sudo ./capture firmware.bin scan.pgm
```

先將手指移開，看到 `Place finger on sensor` 再放上。初始化失敗時，先拔插模組再重試。

要測試 x86 比對引擎，另外安裝工具並建置：

```bash
sudo apt install gcc-x86-64-linux-gnu libc6-dev-amd64-cross qemu-user cabextract
bash build.sh --with-matcher
sudo timeout 30s qemu-x86_64 ./matcher-x86_64 \
  ./matcher-blobs/ftWbioEngineAdapter.dll smoke ./scan.pgm
```

`IMAGE_ACCEPTED` 只表示引擎接受影像，不表示辨識正確。

## 開發測試

```bash
sudo python3 test-recognition.py
```

此程式會錄入同指影像，再做同指與異指測試。資料存入獨立的 `recognition-*` 目錄；目錄權限為 `0700`，檔案為私人權限。中止後保留資料供除錯。

已有測試資料可繼續使用，將 `/path/to/session` 換成程式顯示的目錄：

```bash
sudo python3 test-recognition.py --resume /path/to/session
sudo python3 replay-verification.py /path/to/session
sudo python3 replay-verification.py --internal /path/to/session
sudo python3 diagnose-session.py /path/to/session
sudo python3 test-preprocessing.py /path/to/session
```

`--internal` 是針對固定 DLL 版本的反組譯診斷，會額外執行一次底層比對，不能當作登入判定。它可能受引擎內部狀態影響。

## 相容性修改

- 以 ARM64 libusb 實作獨立擷取程式。
- 將 x86 比對引擎拆成靜態 helper，由 QEMU 執行。
- 相容舊核心的記憶體保留方式與舊版 QEMU 缺少的 `memfd_create`。
- 修正比對函式的輸出參數順序與 64 位元長度型別，並檢查錯誤回傳。
- 錄入累積 18 個有效樣本後嘗試廠商的正式提交操作，只有提交成功才儲存範本。
- 補齊上游對比拉伸步驟；既有測試影像拉伸前後相同，因此這項差異不是目前誤判的原因。

## 原始碼、授權與資料

上游來源、固定版本與著作權見 [UPSTREAM.md](UPSTREAM.md)，程式碼授權見 [LICENSE](LICENSE)。

本 repo 不包含指紋影像、範本、個人測試紀錄、廠商 DLL 或韌體。準備腳本會在本機下載廠商檔案；沒有將 amd64 套件安裝進 ARM64 系統。
