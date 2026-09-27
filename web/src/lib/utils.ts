import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind 类名：后写的同类属性覆盖先写的，而不是两个都留在 class 里。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
