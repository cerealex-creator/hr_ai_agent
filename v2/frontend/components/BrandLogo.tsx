import Image from "next/image";

type Props = {
  size?: number;
  className?: string;
};

/** Brand mark next to «HR-помогатор». */
export function BrandLogo({ size = 36, className = "" }: Props) {
  return (
    <Image
      src="/logo.png"
      alt=""
      width={size}
      height={size}
      className={`brand-logo${className ? ` ${className}` : ""}`}
      priority
    />
  );
}
