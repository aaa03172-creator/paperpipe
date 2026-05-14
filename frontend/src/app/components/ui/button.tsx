import { ButtonHTMLAttributes, forwardRef } from "react";
import { buttonClassName, ButtonSize, ButtonVariant } from "./buttonClassName";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "default", size = "default", type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClassName({ className, variant, size })}
      {...props}
    />
  );
});
