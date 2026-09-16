import { describe, it, expect } from 'vitest'
import { parseSrt } from '../utils/srt.js'

describe('parseSrt', () => {
  it('parses a normal SRT file', () => {
    const text = `1
00:00:01,200 --> 00:00:04,500
Line one

2
00:00:05,000 --> 00:00:08,000
Line two
Line two-b`

    const cues = parseSrt(text)
    expect(cues).toHaveLength(2)
    expect(cues[0]).toEqual({ start: 1.2, end: 4.5, text: 'Line one' })
    expect(cues[1]).toEqual({ start: 5, end: 8, text: 'Line two\nLine two-b' })
  })

  it('handles BOM and CRLF line endings', () => {
    const text = '\uFEFF1\r\n00:00:01,000 --> 00:00:03,000\r\nBOM and CRLF\r\n'
    const cues = parseSrt(text)
    expect(cues).toHaveLength(1)
    expect(cues[0]).toEqual({ start: 1, end: 3, text: 'BOM and CRLF' })
  })

  it('skips blocks with bad timestamps', () => {
    const text = `1
00:00:01,000 --> 00:00:03,000
Good

2
not a timestamp
Skipped

3
00:00:05,000 --> 00:00:04,000
Inverted`

    const cues = parseSrt(text)
    expect(cues).toHaveLength(1)
    expect(cues[0].text).toBe('Good')
  })

  it('returns an empty array for empty or missing text', () => {
    expect(parseSrt('')).toEqual([])
    expect(parseSrt(null)).toEqual([])
    expect(parseSrt(undefined)).toEqual([])
  })

  it('works without numeric index lines', () => {
    const text = `00:00:01,000 --> 00:00:03,000
No index

00:00:04,000 --> 00:00:06,000
Also no index`
    const cues = parseSrt(text)
    expect(cues).toHaveLength(2)
    expect(cues[1].text).toBe('Also no index')
  })
})
