import axios from "axios";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://backend:5000/api",
});

export default API;
