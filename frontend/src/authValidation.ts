export function validateEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? '' : '请输入有效的电子邮箱地址'
}

export function validateName(name: string) {
  const length = Array.from(name).length
  if (length < 1 || length > 50) return '姓名需为 1–50 个字符'
  if (/[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/u.test(name)) return '姓名不能包含控制字符或不可显示字符'
  return ''
}

export function validatePassword(password: string) {
  const length = Array.from(password).length
  if (length < 15 || length > 128) return '密码需为 15–128 个字符'
  if (!password.trim()) return '密码不能全部为空白'
  return ''
}
