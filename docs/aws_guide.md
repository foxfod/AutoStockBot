# AWS 클라우드 배포 가이드 (AWS Deployment Guide)

안정적인 24시간 운영을 위해 **AWS EC2 (Elastic Compute Cloud)** 서비스를 사용하는 것을 추천합니다.
프리 티어(Free Tier)를 적극 활용하면 1년간 무료(월 750시간)로 운영할 수 있습니다.

## 1단계: AWS EC2 인스턴스 생성
1. **AWS 로그인** 후 'EC2' 서비스 접속 -> **[인스턴스 시작]** 클릭.
2. **이름**: `ScalpingBot` 등 식별 가능한 이름 입력.
3. **OS(AMI)**: `Ubuntu Server 22.04 LTS` (또는 20.04) 선택. (가장 무난하고 자료가 많습니다)
4. **인스턴스 유형**: `t2.micro` (프리 티어 사용 가능) 선택.
5. **키 페어**: [새 키 페어 생성] -> `.pem` 파일 다운로드 (잃어버리면 안 됩니다!).
6. **[인스턴스 시작]** 클릭.

## 2단계: 서버 접속 (SSH)
1. 다운로드 받은 `.pem` 키 파일이 있는 폴더에서 터미널(PowerShell 또는 CMD)을 엽니다.
2. 다음 명령어로 접속합니다:
    ```bash
    ssh -i "내키파일.pem" ubuntu@<퍼블릭_IPv4_주소>
    ```
    *(윈도우 10 이상은 기본 ssh 명령어를 지원합니다. 접속이 안 되면 PuTTY 등을 사용하세요)*

    > [!WARNING]
    > **Windows "Permissions are too open" 오류 해결**
    > `.pem` 파일 권한 문제로 접속이 안 될 경우, 해당 파일이 있는 폴더에서 다음 3줄의 명령어를 한 줄씩 입력하여 권한을 수정하세요:
    > ```powershell
    > icacls "키파일.pem" /reset
    > icacls "키파일.pem" /grant:r "$($env:USERNAME):R"
    > icacls "키파일.pem" /inheritance:r
    > ```

## 3단계: 환경 설정 (Ubuntu)
접속된 서버 터미널에서 다음 명령어들을 순서대로 입력하여 환경을 구축합니다.

### A. 시스템 업데이트 및 Python/Git 설치
```bash
sudo apt update
sudo apt install python3-pip python3-venv git -y
```

### B. 타임존 설정 (한국 시간)
이 시스템은 한국 시간(KST) 09:00에 동작해야 하므로 서버 시간을 한국으로 맞춥니다.
```bash
sudo timedatectl set-timezone Asia/Seoul
date
# (출력: 2026. 02. 03. 15:00:00 KST 확인)
```

## 4단계: 코드 배포

### A. 프로젝트 복사
GitHub를 사용 중이라면 `git clone`이 가장 편합니다. 아니라면 로컬 파일을 전송해야 합니다.
```bash
# GitHub 예시
git clone https://github.com/사용자명/레포지토리명.git
cd 레포지토리명
```
*(GitHub 없으면 로컬에서 `scp` 명령어로 파일 전송)*

### B. 가상환경 구성
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### C. .env 파일 생성
서버에는 `.env` 파일이 없으므로 직접 만들어야 합니다.
```bash
nano .env
```
*(로컬의 .env 내용을 복사해서 붙여넣고, `Ctrl+O` -> `Enter` -> `Ctrl+X` 로 저장)*

## 5단계: 무중단 실행 설정 (Systemd)
터미널을 꺼도 프로그램이 계속 돌고, 재부팅 해도 자동으로 시작되게 하려면 `systemd`를 씁니다.

1. 서비스 파일 생성:
```bash
sudo nano /etc/systemd/system/scalping_bot.service
```

2. 아래 내용 붙여넣기 (경로는 사용자 환경에 맞게 수정):
```ini
[Unit]
Description=Scalping Stock Bot
After=network.target

[Service]
# 사용자명 (Ubuntu 기본은 ubuntu)
User=ubuntu
# 프로젝트 경로
WorkingDirectory=/home/ubuntu/레포지토리폴더명
# 실행 명령어 (venv 파이썬 절대경로)
ExecStart=/home/ubuntu/레포지토리폴더명/venv/bin/python main_auto_trade.py
# 자동 재시작
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. 서비스 등록 및 시작:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scalping_bot
sudo systemctl start scalping_bot
```

4. 상태 확인:
```bash
sudo systemctl status scalping_bot
```
(`active (running)`이 뜨면 성공입니다!)

---
**이제 터미널을 꺼도 봇은 24시간 쉬지 않고 돌아갑니다.**
텔레그램으로 오는 "System Started" 알림을 확인하세요.
