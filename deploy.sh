#!/bin/bash
# deploy_honeystream.sh
# Run on a fresh EC2 Ubuntu instance

# === 1️⃣ Update system packages ===
sudo apt update && sudo apt upgrade -y

# === 2️⃣ Install essentials ===
sudo apt install -y curl build-essential git sqlite3

# === 3️⃣ Install Node.js 22.x ===
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v

# === 4️⃣ Install PM2 globally ===
sudo npm install -g pm2

# === 5️⃣ Clone project (replace with your repo) ===
cd ~
git clone https://github.com/G-cae78/ProtectTheHoney.git honeystream
cd honeystream

# === 6️⃣ Install backend dependencies ===
cd backend
npm install

# Ensure DB will initialize automatically via db.js
if [ ! -f "honeystream.db" ]; then
  touch honeystream.db
  echo "SQLite DB file created"
fi

# Start backend with PM2
pm2 start index.js --name honeystream-backend
pm2 save
pm2 startup

# === 7️⃣ Build and serve frontend ===
cd ../frontend
npm install
npm run build

# Install 'serve' if not already installed
sudo npm install -g serve

# Start frontend in background using PM2
pm2 start "serve -s build -l 4173" --name honeystream-frontend
pm2 save

# === 8️⃣ Done ===
echo "✅ Deployment complete!"
echo "Backend running on port 3000"
echo "Frontend running on port 4173"
