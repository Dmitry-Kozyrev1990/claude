export interface Env {
  DB: D1Database;
  BOT_TOKEN: string;
  WEBHOOK_SECRET: string;
  /** Telegram id админов через запятую */
  ADMIN_IDS: string;
  BOT_USERNAME: string;
  /** username (без @), кому писать для оплаты и вопросов */
  SUPPORT_USERNAME: string;
}

export type Age = "a7_9" | "a10_12" | "a13_14" | "multi";

export interface Lesson {
  title: string;
  minutes: number;
  /** HTML для Telegram: <b>, <i>, <a>. Без экрана — пометка в тексте. */
  text: string;
}

export interface Course {
  id: string;
  title: string;
  age: string; // «от 7 лет»
  price: number; // рубли
  pitch: string;
  format: string;
  needs: string;
  result: string;
  lessons: Lesson[];
  /** для пакета: какие курсы открывает */
  includes?: string[];
}
