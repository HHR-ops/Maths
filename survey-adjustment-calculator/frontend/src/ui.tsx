// Button variants follow shadcn/ui's component pattern. See THIRD_PARTY_NOTICES.md.
import * as React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'
import { X } from 'lucide-react'

const buttonVariants = cva('button', { variants: { variant: { default: 'button-primary', outline: 'button-outline', ghost: 'button-ghost', danger: 'button-danger' }, size: { default: '', sm: 'button-sm', icon: 'button-icon' } }, defaultVariants: { variant: 'outline', size: 'default' } })
export function Button({ className, variant, size, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>) {
  return <button className={clsx(buttonVariants({ variant, size }), className)} {...props} />
}
export function Modal({ open, title, description, children, onClose, wide = false }: { open: boolean; title: string; description?: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  return <Dialog.Root open={open} onOpenChange={v => { if (!v) onClose() }}><Dialog.Portal><Dialog.Overlay className="modal-overlay" /><Dialog.Content className={clsx('modal', wide && 'modal-wide')}><Dialog.Title className="modal-title">{title}</Dialog.Title><Dialog.Description className="modal-description">{description || '填写信息后保存。'}</Dialog.Description><Dialog.Close asChild><Button variant="ghost" size="icon" className="modal-close" aria-label="关闭"><X size={17} /></Button></Dialog.Close>{children}</Dialog.Content></Dialog.Portal></Dialog.Root>
}
export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}
export function Empty({ title, text }: { title: string; text?: string }) {
  return <div className="empty"><div className="empty-symbol">＋</div><strong>{title}</strong>{text && <span>{text}</span>}</div>
}
