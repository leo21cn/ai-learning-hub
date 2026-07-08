import type { CSSProperties } from "react";

interface LogoProps {
  /** 图标尺寸（像素），同时按比例决定文字大小 */
  size?: number;
  /** 是否显示文字 "Learning Hub" */
  showText?: boolean;
  /** 文字颜色类名（Tailwind） */
  textClassName?: string;
  /** 根节点额外类名 */
  className?: string;
  /** 整体风格变体：horizontal 横向、stacked 纵向堆叠 */
  variant?: "horizontal" | "stacked";
}

/**
 * Learning Hub 品牌 Logo
 *
 * - 蓝色 #2563eb 圆角矩形背景
 * - 顶部 hub 节点网络 + 底部打开的书本（学习）
 * - 适配 favicon / Header / 登录页等场景，通过 size 控制尺寸
 */
export function Logo({
  size = 40,
  showText = true,
  textClassName = "text-slate-900",
  className = "",
  variant = "horizontal",
}: LogoProps) {
  const textSize = Math.round(size * 0.65);
  const gap = Math.round(size * 0.3);
  const wrapperStyle: CSSProperties = {
    gap,
    lineHeight: 1,
    flexDirection: variant === "stacked" ? "column" : "row",
  };

  return (
    <div
      className={`inline-flex items-center ${className}`}
      style={wrapperStyle}
      data-testid="brand-logo"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 64 64"
        role="img"
        aria-label="Learning Hub"
      >
        <rect width="64" height="64" rx="14" fill="#2563eb" />
        <g stroke="#ffffff" strokeWidth="2" strokeLinecap="round">
          <line x1="20" y1="16" x2="29" y2="19" />
          <line x1="44" y1="16" x2="35" y2="19" />
        </g>
        <circle cx="32" cy="20" r="4" fill="#ffffff" />
        <circle cx="18" cy="14" r="3" fill="#ffffff" />
        <circle cx="46" cy="14" r="3" fill="#ffffff" />
        <path
          d="M14 38 C22 33,30 35,32 40 C34 35,42 33,50 38 L50 52 C42 48,34 50,32 54 C30 50,22 48,14 52 Z"
          fill="#ffffff"
        />
      </svg>
      {showText && (
        <span
          className={`font-bold tracking-tight whitespace-nowrap ${textClassName}`}
          style={{ fontSize: textSize }}
        >
          Learning Hub
        </span>
      )}
    </div>
  );
}
