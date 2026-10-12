import { expect, test } from 'vitest'
import { formatTime } from '../time'

test('formatTime 去掉 ISO 串中间的 T', () => {
  expect(formatTime('2026-10-12T21:49:14')).toBe('2026-10-12 21:49:14')
})

test('formatTime 空值返回破折号', () => {
  expect(formatTime(undefined)).toBe('—')
  expect(formatTime(null)).toBe('—')
  expect(formatTime('')).toBe('—')
})
