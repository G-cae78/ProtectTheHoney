require('dotenv').config();
const express = require('express');
const cors = require('cors');
const mariadb = require('mariadb');
const bcrypt = require('bcryptjs');

const PORT = process.env.API_PORT ? Number(process.env.API_PORT) : 4000;

const pool = mariadb.createPool({
  host: process.env.DB_HOST || '127.0.0.1',
  port: process.env.DB_PORT ? Number(process.env.DB_PORT) : 3306,
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'examplepassword',
  database: process.env.DB_NAME || 'moreehoney',
  connectionLimit: 5,
});

async function ensureSchema() {
  const conn = await pool.getConnection();
  try {
    await conn.query(`
      CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(100) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      ) ENGINE=InnoDB;
    `);

    await conn.query(`
      CREATE TABLE IF NOT EXISTS admins (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(100) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      ) ENGINE=InnoDB;
    `);

    // Insert dummy user if none exist
    const users = await conn.query("SELECT id FROM users LIMIT 1");
    if (!users || users.length === 0) {
      const pw = await bcrypt.hash('password123', 10);
      await conn.query("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", ['johndoe', 'john@example.com', pw]);
      await conn.query("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", ['janedoe', 'jane@example.com', pw]);
      console.log('Inserted dummy users');
    }

    const admins = await conn.query("SELECT id FROM admins LIMIT 1");
    if (!admins || admins.length === 0) {
      const apw = await bcrypt.hash('adminpass', 10);
      await conn.query("INSERT INTO admins (username, email, password) VALUES (?, ?, ?)", ['admin', 'admin@example.com', apw]);
      console.log('Inserted dummy admin');
    }
  } finally {
    if (conn) conn.release();
  }
}

const app = express();
app.use(cors());
app.use(express.json());

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

app.post('/api/login', async (req, res) => {
  const { username, email, password } = req.body || {};
  if (!password || (!username && !email)) {
    return res.status(400).json({ message: 'Missing credentials' });
  }

  const conn = await pool.getConnection();
  try {
    const row = await conn.query("SELECT id, username, email, password FROM users WHERE username = ? OR email = ? LIMIT 1", [username || null, email || null]);
    if (!row || row.length === 0) return res.status(401).json({ message: 'Invalid credentials' });
    const user = row[0];
    const match = await bcrypt.compare(password, user.password);
    if (!match) return res.status(401).json({ message: 'Invalid credentials' });

    // success - return user summary (no password)
    return res.json({ id: user.id, username: user.username, email: user.email });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ message: 'Server error' });
  } finally {
    if (conn) conn.release();
  }
});

app.post('/api/admin/login', async (req, res) => {
  const { username, email, password } = req.body || {};
  if (!password || (!username && !email)) {
    return res.status(400).json({ message: 'Missing credentials' });
  }

  const conn = await pool.getConnection();
  try {
    const row = await conn.query("SELECT id, username, email, password FROM admins WHERE username = ? OR email = ? LIMIT 1", [username || null, email || null]);
    if (!row || row.length === 0) return res.status(401).json({ message: 'Invalid credentials' });
    const admin = row[0];
    const match = await bcrypt.compare(password, admin.password);
    if (!match) return res.status(401).json({ message: 'Invalid credentials' });
    return res.json({ id: admin.id, username: admin.username, email: admin.email, admin: true });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ message: 'Server error' });
  } finally {
    if (conn) conn.release();
  }
});

// debug route to list users (dev only)
app.get('/api/users', async (req, res) => {
  const conn = await pool.getConnection();
  try {
    const rows = await conn.query('SELECT id, username, email, created_at FROM users');
    res.json(rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Server error' });
  } finally {
    if (conn) conn.release();
  }
});

// start server after ensuring schema
ensureSchema()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`API server listening on port ${PORT}`);
    });
  })
  .catch((err) => {
    console.error('Failed to initialize database schema:', err);
    process.exit(1);
  });
