const express = require('express');
const bodyParser = require('body-parser');
const bcrypt = require('bcryptjs');
const db = require('./db');
const cors = require('cors');

const app = express();

// CORS middleware - let it handle headers
app.use(cors({
  origin: '*', 
  credentials: false,
}));
app.use(bodyParser.json());

// Register
app.post('/api/auth/register', (req, res) => {
  const { username, email, password } = req.body;
  if (!email || !password) return res.status(400).json({ error: 'email and password required' });

  bcrypt.hash(password, 10, (err, hash) => {
    if (err) return res.status(500).json({ error: 'hash error' });

    const sql = 'INSERT INTO users (username, email, password) VALUES (?, ?, ?)';
    db.run(sql, [username || null, email, hash], function(insertErr) {
      if (insertErr) {
        if (insertErr.message.includes('UNIQUE')) return res.status(409).json({ error: 'email exists' });
        console.error(insertErr);
        return res.status(500).json({ error: 'db error' });
      }
      // Send response after everything is ready
      res.status(201).json({ id: this.lastID, username, email });
    });
  });
});

// Login
app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ error: 'email and password required' });

  const sql = 'SELECT id, username, email, password FROM users WHERE email = ? LIMIT 1';
  db.get(sql, [email], (err, row) => {
    if (err) return res.status(500).json({ error: 'db error' });
    if (!row) return res.status(401).json({ error: 'invalid credentials' });

    bcrypt.compare(password, row.password, (cmpErr, ok) => {
      if (cmpErr) return res.status(500).json({ error: 'compare error' });
      if (!ok) return res.status(401).json({ error: 'invalid credentials' });

      res.json({ id: row.id, username: row.username, email: row.email, msg: 'authenticated' });
    });
  });
});

// List users
app.get('/api/users', (req, res) => {
  db.all('SELECT id, username, email, created_at FROM users ORDER BY id DESC LIMIT 100', [], (err, rows) => {
    if (err) return res.status(500).json({ error: 'db error' });
    res.json(rows);
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`App listening on port ${PORT}`));
