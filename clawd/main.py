import os
import logging
import asyncio
import psutil
import psycopg2
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clawd_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "clawd_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

async def check_admin(update: Update):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    await update.message.reply_text(
        "👋 안녕하세요! Clawd-Bot입니다.\n"
        "당신의 VPS에서 가동 중입니다.\n\n"
        "명령어:\n"
        "/brief - 오늘 건강 요약\n"
        "/status - 서버 상태 확인\n"
        "/help - 도움말"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    
    msg = (
        "🖥 **서버 상태**\n"
        f"- CPU 사용률: {cpu}%\n"
        f"- 메모리 사용률: {mem}%\n"
        f"- 디스크 사용률: {disk}%\n"
        f"- 시스템 부팅일: {boot_time}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    
    await update.message.reply_chat_action("typing")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 최근 2일 데이터를 가져옴 (오늘, 어제)
        cur.execute("SELECT * FROM health_daily ORDER BY date DESC LIMIT 2")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        if rows:
            # 기본적으로 가장 최근 데이터(오늘 아침 일어난 기록)를 타겟으로 잡음
            # 가민 API 특성상 1월 26일 데이터는 25일 밤~26일 아침 수면을 의미함
            target = rows[0]
            
            # 만약 오늘 데이터 로우는 생겼는데 아직 수면 정보가 없다면(자고 있는 중이거나 연동 지연), 
            # 어제 확정된 데이터를 보여줌
            if len(rows) > 1 and (target[1] is None or target[1] == 0):
                target = rows[1]
                note = "(오늘 데이터 미확정으로 어제 기록 출력)"
            else:
                note = ""

            date = target[0]
            sleep_h = target[1]
            sleep_s = target[2]
            rhr = target[3]
            hrv = target[4]
            stress = target[5]
            
            msg = (
                f"📊 **건강 브리핑 ({date})** {note}\n\n"
                f"💤 수면: {sleep_h}시간 (점수: {sleep_s})\n"
                f"💓 안정 시 심박수: {rhr} bpm\n"
                f"📈 HRV 상태: {hrv}\n"
                f"😫 평균 스트레스: {stress}\n\n"
                "가장 최근 확정된 데이터 기준입니다."
            )
        else:
            msg = "데이터가 아직 수집되지 않았습니다. Garmin 워커가 작동 중인지 확인해주세요."
            
    except Exception as e:
        msg = f"❌ 데이터 조회 중 오류 발생: {e}"
        logger.error(msg)
        
    await update.message.reply_text(msg, parse_mode='Markdown')

if __name__ == '__main__':
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        exit(1)

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('brief', brief))
    
    logger.info("Bot started and waiting for messages...")
    application.run_polling()
