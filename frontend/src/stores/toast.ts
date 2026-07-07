import { create } from "zustand";

type ToastKind = "info" | "success" | "error";

type ToastItem = { id: number; kind: ToastKind; message: string };

type ToastState = {
  items: ToastItem[];
  push: (message: string, kind?: ToastKind) => void;
  dismiss: (id: number) => void;
};

let _seq = 1;

export const useToastStore = create<ToastState>((set) => ({
  items: [],
  push: (message, kind = "info") => {
    const id = _seq++;
    set((s) => ({ items: [...s.items, { id, kind, message }] }));
    setTimeout(() => {
      set((s) => ({ items: s.items.filter((i) => i.id !== id) }));
    }, 3500);
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
}));

export function toast(message: string, kind: ToastKind = "info") {
  useToastStore.getState().push(message, kind);
}
