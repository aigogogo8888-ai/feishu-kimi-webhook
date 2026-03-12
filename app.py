"""
Feishu Webhook Server for Render
"""
import json
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a92f1b744a61de1a")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

@app.route('/')
def health_check():
    return jsonify({"status": "Feishu Webhook Server OK"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        if 'challenge' in data:
            return jsonify({"challenge": data.get('challenge', '')})
        
        event_type = data.get('header', {}).get('event_type', '')
        
        if event_type == 'im.message.receive_v1':
            event = data.get('event', {})
            message = event.get('message', {})
            sender = event.get('sender', {}).get('sender_id', {}).get('open_id', '')
            content = json.loads(message.get('content', '{}'))
            text = content.get('text', '')
            
            response = process_command(text.strip(), sender)
            if response:
                reply_to_feishu(message.get('message_id', ''), response)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def process_command(text: str, sender_id: str) -> str:
    text = text.lower().strip()
    
    if text.startswith('/task '):
        return handle_task(text[6:].strip(), sender_id)
    elif text.startswith('/help'):
        return "🤖 Commands: /task <description>, /task KIMI K2.5 <prompt>"
    return None

def handle_task(task: str, sender_id: str) -> str:
    import threading
    from datetime import datetime
    
    task_id = f"TASK_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if any(kw in task.lower() for kw in ['kimi', 'k2.5']):
        prompt = task
        for kw in ['kimi k2.5', 'kimi', 'k2.5', '請使用', '使用', '幫我', '請']:
            prompt = prompt.replace(kw, '').strip()
        
        threading.Thread(target=run_kimi_generation, 
                        args=(prompt, sender_id, task_id), 
                        daemon=True).start()
        
        return f"🤖 KIMI K2.5 任務已接收！\n📋 Task ID: {task_id}\n⏳ 生成中..."
    
    return f"✅ Task Created!\nID: {task_id}\nDescription: {task}"

def run_kimi_generation(prompt: str, sender_id: str, task_id: str):
    try:
        result = call_kimi_api(prompt)
        message = f"✅ KIMI K2.5 完成！\n\n{result[:500]}..."
        send_feishu_message(sender_id, message)
    except Exception as e:
        send_feishu_message(sender_id, f"❌ 失敗: {str(e)}")

def call_kimi_api(prompt: str) -> str:
    api_key = os.getenv("KIMI_API_KEY", "")
    if not api_key:
        return "⚠️ KIMI_API_KEY 未設定"
    
    response = requests.post(
        "https://api.moonshot.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "kimi-k2.5",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        },
        timeout=120
    )
    return response.json()['choices'][0]['message']['content']

def reply_to_feishu(message_id: str, content: str):
    token = get_feishu_token()
    if token:
        requests.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"content": json.dumps({"text": content})}
        )

def send_feishu_message(user_id: str, content: str):
    token = get_feishu_token()
    if token:
        requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"receive_id": user_id, "content": json.dumps({"text": content}), "msg_type": "text"},
            params={"receive_id_type": "open_id"}
        )

def get_feishu_token() -> str:
    try:
        response = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
        )
        return response.json().get("tenant_access_token", "")
    except:
        return ""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
