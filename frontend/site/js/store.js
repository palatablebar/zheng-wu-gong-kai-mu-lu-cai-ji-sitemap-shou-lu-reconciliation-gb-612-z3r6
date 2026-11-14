import { BRAND } from './config.js';

const TOKEN_KEY = `${BRAND.short}.token`;
const USER_KEY = `${BRAND.short}.user`;

export const session = {
  token() {
    return localStorage.getItem(TOKEN_KEY) || '';
  },
  user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch {
      return null;
    }
  },
  set(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};
