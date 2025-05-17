const express = require('express');
const multer = require('multer');
const fs = require('fs');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');
const { writeTextToFile } = require('./text_writer');
const axios = require('axios');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const ensureDirExists = (dir) => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
};

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    let folder = 'others';

    if (file.mimetype.startsWith('image/')) folder = 'images';
    else if (file.mimetype.startsWith('video/')) folder = 'video';
    else if (file.mimetype.startsWith('audio/')) folder = 'audio';
    else if (file.mimetype === 'application/pdf') folder = 'pdf';

    const fullPath = path.join(__dirname, 'uploads', folder);
    ensureDirExists(fullPath);
    cb(null, fullPath);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    const uniqueName = `${Date.now()}_${Math.round(Math.random() * 1E9)}${ext}`;
    cb(null, uniqueName);
  },
});

const upload = multer({ storage });

app.post('/uploadMedia', upload.single('file'), (req, res) => {
  if (!req.file) return res.status(400).send('No file uploaded');
  res.send(`File uploaded to ${req.file.path}`);
});

app.post('/uploadText', (req, res) => {
  const { text } = req.body;
  if (!text) return res.status(400).send('No text provided');

  const folder = path.join(__dirname, 'uploads', 'text');
  ensureDirExists(folder);

  const filePath = path.join(folder, `${Date.now()}_text.txt`);
  fs.writeFileSync(filePath, text);
  res.send('Text saved to ' + filePath);
});

app.post('/processAudio', upload.single('file'), (req, res) => {
  const filePath = req.file.path;

  res.sendFile(path.resolve(filePath), err => {
    fs.unlink(filePath, () => {});
  });
});

app.post('/processText', async (req, res) => {
  console.log('Processing text');
  const { text } = req.body;
  if (!text) return res.status(400).send('No text provided');
  console.log('Processing text: ' + text);
  
  writeTextToFile(text, `text_request_${Date.now()}.txt`);
  
  try {
    const memoryApiUrl = 'http://localhost:5000/query';
    const memoryResponse = await axios.post(memoryApiUrl, { query: text });
    
    if (memoryResponse.data && memoryResponse.data.success) {
      console.log('Memory API response:', memoryResponse.data.memory);
    }
  } catch (error) {
    console.error('Error calling memory API:', error.message);
  }
  
  const staticAudioPath = path.resolve(__dirname, 'sample.wav');
  if (fs.existsSync(staticAudioPath)) {
    console.log('Audio file found, sending response');
    res.sendFile(staticAudioPath);
  } else {
    console.log('Audio file NOT found!');
    res.status(404).send('TTS sample audio not found');
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});
