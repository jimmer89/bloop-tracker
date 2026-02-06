#!/bin/bash
# Iniciar Bloop Tracker con túnel Serveo

cd ~/clawd/bloop-tracker
source venv/bin/activate

# Iniciar servidor en background
echo "🚀 Iniciando webhook server..."
python webhook_server.py &
SERVER_PID=$!
sleep 2

# Iniciar túnel Serveo
echo "🌐 Conectando túnel Serveo..."
ssh -R 03663803c8608bec:80:localhost:5555 serveo.net

# Cleanup
kill $SERVER_PID 2>/dev/null
