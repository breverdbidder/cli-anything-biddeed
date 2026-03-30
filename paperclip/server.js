'use strict';
const express = require('express');
const { Pool } = require('pg');

const app = express();
app.use(express.json());

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://paperclip:paperclip@db:5432/paperclip'
});

// HTML pages
app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html><head><title>Paperclip</title></head>
<body>
<h1>Paperclip — Task Management</h1>
<nav><a href="/tasks">Tasks</a> | <a href="/login">Login</a></nav>
</body></html>`);
});

app.get('/tasks', (req, res) => {
  res.send(`<!DOCTYPE html>
<html><head><title>Tasks — Paperclip</title></head>
<body><h1>Tasks</h1></body></html>`);
});

app.get('/login', (req, res) => {
  res.send(`<!DOCTYPE html>
<html><head><title>Login — Paperclip</title></head>
<body><h1>Login</h1>
<form method="post" action="/login">
  <input type="text" name="username" placeholder="Username" />
  <input type="password" name="password" placeholder="Password" />
  <button type="submit">Login</button>
</form>
</body></html>`);
});

// API routes
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', ts: new Date().toISOString(), service: 'paperclip' });
});

app.get('/api/tasks', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100');
    res.json({ tasks: result.rows });
  } catch (err) {
    res.json({ tasks: [], error: err.message });
  }
});

app.post('/api/tasks', async (req, res) => {
  const { title, description } = req.body;
  if (!title) return res.status(400).json({ error: 'title required' });
  try {
    const result = await pool.query(
      'INSERT INTO tasks(title, description) VALUES($1, $2) RETURNING *',
      [title, description || '']
    );
    res.status(201).json({ task: result.rows[0] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/login', (req, res) => {
  res.redirect('/tasks');
});

const PORT = process.env.PORT || 3100;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Paperclip running on port ${PORT}`);
});
