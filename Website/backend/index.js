const express = require('express');
const bodyParser = require('body-parser');
const bcrypt = require('bcryptjs');
const db = require('./db');
const cors = require('cors');

const app = express();
app.use(cors({
  origin: '*' ,// your React dev server
  credentials: false, // if you plan to send cookies
}));
app.use(bodyParser.json());

// Register - creates a user (email + password)
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
      res.status(201).json({ id: this.lastID, username, email });
      res.setHeader('Access-Control-Allow-Origin', '*');
    });
  });
});

// Login - simple password check
app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ error: 'email and password required' });

  const sql = 'SELECT id, username, email, password FROM users WHERE email = ? LIMIT 1';
  db.get(sql, [email], (err, row) => {
    if (err) {
      console.error(err);
      return res.status(500).json({ error: 'db error' });
    }
    if (!row) return res.status(401).json({ error: 'invalid credentials' });

    bcrypt.compare(password, row.password, (cmpErr, ok) => {
      if (cmpErr) return res.status(500).json({ error: 'compare error' });
      if (!ok) return res.status(401).json({ error: 'invalid credentials' });

      res.json({ id: row.id, username: row.username, email: row.email, msg: 'authenticated' });
      res.setHeader('Access-Control-Allow-Origin', '*');
    });
  });
});

// List users (ids + usernames only)
app.get('/api/users', (req, res) => {
  const sql = 'SELECT id, username, email, created_at FROM users ORDER BY id DESC LIMIT 100';
  db.all(sql, [], (err, rows) => {
    if (err) {
      console.error(err);
      return res.status(500).json({ error: 'db error' });
    }
    res.json(rows);
    res.setHeader('Access-Control-Allow-Origin', '*');
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`App listening on port ${PORT}`));
