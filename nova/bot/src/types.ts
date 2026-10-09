export interface Env {
  DB: D1Database;
  BOT_TOKEN: string;
  WEBHOOK_SECRET: string;
  YK_SHOP_ID: string;
  YK_SECRET_KEY: string;
  ADMIN_ID: string;
  BOT_USERNAME: string;
  SUPPORT_USERNAME: string;
  VAT_CODE: string;
}

export type Segment = "self" | "parents" | "kids" | "family";

export interface Course {
  id: string;
  title: string;
  segments: Segment[];
  price: number; // рубли
  pitch: string; // короткое описание для карточки
  program: string[];
  /** id закрытого канала/группы (бот — админ), выдаётся одноразовая ссылка. */
  accessChatId?: number;
  /** запасной вариант: фиксированная ссылка на материалы */
  accessUrl?: string;
}
