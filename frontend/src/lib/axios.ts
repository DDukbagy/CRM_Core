import axios from 'axios';

// 환경변수에서 주소를 가져옵니다. 없으면 로컬 주소 사용.
const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;