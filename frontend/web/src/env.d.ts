declare namespace App {
  interface Locals {
    /** 当前登录用户；未登录为 null（由 middleware 填充） */
    user: import("./lib/session").SessionUser | null;
  }
}
