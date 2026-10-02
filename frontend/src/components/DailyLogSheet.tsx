import { Box, Paper, Stack, Typography } from '@mui/material'
import type { DailyLog, DutyStatus } from '../types'

type Props = {
  log: DailyLog
}

const statusRows: DutyStatus[] = ['OFF_DUTY', 'SLEEPER_BERTH', 'DRIVING', 'ON_DUTY_NOT_DRIVING']
const rowLabels: Record<DutyStatus, string> = {
  OFF_DUTY: '1. Off Duty',
  SLEEPER_BERTH: '2. Sleeper Berth',
  DRIVING: '3. Driving',
  ON_DUTY_NOT_DRIVING: '4. On Duty (Not Driving)',
}
const rowY: Record<DutyStatus, number> = {
  OFF_DUTY: 224,
  SLEEPER_BERTH: 274,
  DRIVING: 324,
  ON_DUTY_NOT_DRIVING: 374,
}
const colors: Record<DutyStatus, string> = {
  OFF_DUTY: '#111827',
  SLEEPER_BERTH: '#7c3aed',
  DRIVING: '#1d4ed8',
  ON_DUTY_NOT_DRIVING: '#b45309',
}

const gridX = 166
const gridY = 184
const gridW = 770
const rowH = 50
const gridH = rowH * 4
const TOTAL_DAY_MINUTES = 24 * 60
const QUARTER_HOUR_MINUTES = 15
const TOTAL_INTERVALS = TOTAL_DAY_MINUTES / QUARTER_HOUR_MINUTES
const BASE_VIEW_HEIGHT = 720
const REMARKS_LABEL_Y = 432
const REMARKS_TABLE_X = 52
const REMARKS_TABLE_W = 980
const REMARKS_HEADER_Y = 448
const REMARKS_HEADER_HEIGHT = 26
const REMARKS_FIRST_ROW_Y = 484
const REMARKS_ROW_MIN_HEIGHT = 36
const REMARKS_LINE_HEIGHT = 15
const REMARKS_ITEM_GAP = 7
const REMARKS_DETAIL_MAX_CHARS = 78

type RemarkLayout = {
  items: Array<{
    key: string
    time: string
    status: string
    detailLines: string[]
    y: number
    rowY: number
    rowHeight: number
    tone: string
  }>
  recapY: number
  viewHeight: number
}

export function DailyLogSheet({ log }: Props) {
  const totals = statusRows.map((status) => log.totals[status] ?? 0)
  const remarkLayout = buildRemarkLayout(log.remarks)

  return (
    <Paper className="daily-log-paper" sx={{ p: { xs: 1, sm: 1.5, md: 2 }, overflowX: 'auto', overflowY: 'hidden' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2} sx={{ mb: 1.25 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h3">Driver&apos;s Daily Log</Typography>
          <Typography color="text.secondary" variant="body2" noWrap>
            {formatLogDate(log.date)}
          </Typography>
        </Box>
        <Typography color="#17324d" fontWeight={950} sx={{ flex: '0 0 auto' }}>
          {log.driving_miles} mi
        </Typography>
      </Stack>

      <svg className="daily-log-svg" viewBox={`0 0 1080 ${remarkLayout.viewHeight}`} role="img" aria-label={`Driver daily log for ${log.date}`}>
        <rect x="0" y="0" width="1080" height={remarkLayout.viewHeight} rx="8" fill="#ffffff" />
        <rect x="0" y="0" width="1080" height="78" fill="#f8fafc" />
        <text x="40" y="30" className="svg-kicker">DRIVER RECORD OF DUTY STATUS</text>
        <text x="40" y="58" className="svg-title">Drivers Daily Log</text>
        <text x="458" y="35" className="svg-small-bold">Date</text>
        <text x="458" y="58" className="svg-small">{log.date}</text>
        <text x="730" y="32" className="svg-tiny">Original - File at home terminal</text>
        <text x="730" y="50" className="svg-tiny">Duplicate - Driver retains possession for 8 days</text>

        <Field x={40} y={104} width={218} label="From" value={trim(log.origin, 25)} />
        <Field x={276} y={104} width={218} label="To" value={trim(log.destination, 25)} />
        <Field x={512} y={104} width={172} label="Total Miles Driving Today" value={`${log.driving_miles}`} />
        <Field x={702} y={104} width={330} label="Name of Carrier or Carriers" value="Spotter Assessment Carrier" />

        <DutyGrid />

        {log.segments.map((segment, index) => {
          const startMinute = clampMinute(segment.start_minute)
          const endMinute = clampMinute(segment.end_minute)
          if (endMinute <= startMinute) {
            return null
          }

          const x1 = minuteToX(startMinute)
          const x2 = minuteToX(endMinute)
          const y = rowY[segment.status]
          const previous = log.segments[index - 1]
          return (
            <g key={`${segment.start_time}-${index}`}>
              {previous && previous.status !== segment.status && (
                <line
                  data-duty-transition="true"
                  data-minute={startMinute}
                  x1={x1}
                  x2={x1}
                  y1={rowY[previous.status]}
                  y2={y}
                  stroke="#111827"
                  strokeWidth="2"
                  strokeLinecap="square"
                />
              )}
              <line
                data-duty-segment={segment.status}
                data-start-minute={startMinute}
                data-end-minute={endMinute}
                x1={x1}
                x2={x2}
                y1={y}
                y2={y}
                stroke={colors[segment.status]}
                strokeWidth="5"
                strokeLinecap="square"
              />
            </g>
          )
        })}

        <Totals totals={totals} />
        <Remarks log={log} layout={remarkLayout} />
      </svg>
    </Paper>
  )
}


function DutyGrid() {
  const hours = Array.from({ length: 25 }, (_, index) => index)
  const quarterHourMarks = Array.from({ length: TOTAL_INTERVALS + 1 }, (_, index) => index * QUARTER_HOUR_MINUTES)

  return (
    <g>
      <rect x={gridX} y={gridY - 28} width={gridW} height="28" fill="#111827" />
      <rect x="40" y={gridY - 28} width={gridX - 40} height="28" fill="#111827" />
      <rect x={gridX + gridW} y={gridY - 28} width="96" height="28" fill="#111827" />
      <text x="70" y={gridY - 9} fill="#ffffff" className="svg-small-bold">Duty Status</text>
      <text x={gridX + gridW + 27} y={gridY - 9} fill="#ffffff" className="svg-small-bold">Total</text>

      <rect x="40" y={gridY} width={gridX - 40} height={gridH} fill="#ffffff" stroke="#111827" strokeWidth="1.5" />
      <rect x={gridX} y={gridY} width={gridW} height={gridH} fill="#ffffff" stroke="#111827" strokeWidth="1.5" />
      <rect x={gridX + gridW} y={gridY} width="96" height={gridH} fill="#ffffff" stroke="#111827" strokeWidth="1.5" />

      {statusRows.map((status, index) => {
        const labelLines = rowLabelLines(status)
        const labelY = gridY + (labelLines.length > 1 ? 23 : 32) + index * rowH

        return (
          <g key={status}>
            <text x="52" y={labelY} className="svg-row-label">
              {labelLines.map((line, lineIndex) => (
                <tspan key={line} x="52" dy={lineIndex === 0 ? 0 : 14}>
                  {line}
                </tspan>
              ))}
            </text>
            {index > 0 && (
              <line x1="40" x2={gridX + gridW + 96} y1={gridY + index * rowH} y2={gridY + index * rowH} stroke="#111827" strokeWidth="1" />
            )}
          </g>
        )
      })}

      {quarterHourMarks.map((minute) => {
        const x = minuteToX(minute)
        const isHour = minute % 60 === 0
        const isHalf = minute % 30 === 0
        const lineKind = isHour ? 'hour' : isHalf ? 'half' : 'quarter'
        return (
          <line
            key={minute}
            data-grid-line={lineKind}
            data-minute={minute}
            x1={x}
            x2={x}
            y1={gridY}
            y2={gridY + gridH}
            stroke={isHour ? '#111827' : isHalf ? '#64748b' : '#94a3b8'}
            strokeWidth={isHour ? 1.15 : isHalf ? 0.85 : 0.5}
            opacity={isHour ? 0.9 : isHalf ? 0.65 : 0.42}
          />
        )
      })}

      {hours.map((hour) => (
        <text
          key={hour}
          x={minuteToX(hour * 60)}
          y={gridY - 9}
          textAnchor="middle"
          className={hour === 0 || hour === 24 ? 'svg-time-header svg-time-boundary' : 'svg-time-header'}
        >
          {formatHourLabel(hour)}
        </text>
      ))}
    </g>
  )
}

function Totals({ totals }: { totals: number[] }) {
  const totalHours = totals.reduce((sum, value) => sum + value, 0)

  return (
    <g>
      {statusRows.map((status, index) => (
        <text key={status} x={gridX + gridW + 28} y={gridY + 32 + index * rowH} className="svg-small-bold">
          {totals[index].toFixed(2)}
        </text>
      ))}
      <text x={gridX + gridW + 19} y={gridY + gridH + 27} className="svg-small-bold">
        = {totalHours.toFixed(2)}
      </text>
    </g>
  )
}

function Remarks({ log, layout }: { log: DailyLog; layout: RemarkLayout }) {
  return (
    <g>
      <text x="40" y={REMARKS_LABEL_Y} className="svg-label">Remarks</text>
      <rect
        x={REMARKS_TABLE_X}
        y={REMARKS_HEADER_Y}
        width={REMARKS_TABLE_W}
        height={REMARKS_HEADER_HEIGHT}
        rx="3"
        fill="#f8fafc"
        stroke="#cbd5e1"
      />
      <text x="68" y={REMARKS_HEADER_Y + 17} className="svg-remark-heading">TIME</text>
      <text x="150" y={REMARKS_HEADER_Y + 17} className="svg-remark-heading">DUTY STATUS</text>
      <text x="340" y={REMARKS_HEADER_Y + 17} className="svg-remark-heading">LOCATION / NOTE</text>

      {layout.items.length === 0 ? (
        <text x="68" y={REMARKS_FIRST_ROW_Y + 22} className="svg-remark-detail">
          No duty-status changes recorded for this log.
        </text>
      ) : (
        layout.items.map((item, index) => (
          <g key={item.key} data-remark-row="true">
            <rect
              x={REMARKS_TABLE_X}
              y={item.rowY}
              width={REMARKS_TABLE_W}
              height={item.rowHeight}
              rx="3"
              fill={index % 2 === 0 ? '#ffffff' : '#fbfdff'}
              stroke="#d4deea"
            />
            <circle cx="70" cy={item.y - 4} r="4" fill={item.tone} />
            <text x="88" y={item.y} className="svg-remark-time">{item.time}</text>
            <text x="150" y={item.y} className="svg-remark-status" fill={item.tone}>{item.status}</text>
            <text x="340" y={item.y} className="svg-remark-detail">
              {item.detailLines.map((line, lineIndex) => (
                <tspan key={`${item.key}-${lineIndex}`} x="340" dy={lineIndex === 0 ? 0 : REMARKS_LINE_HEIGHT}>
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        ))
      )}

      <rect x="40" y={layout.recapY} width="992" height="42" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="54" y={layout.recapY + 26} className="svg-small-bold">Recap</text>
      {statusRows.map((status, index) => (
        <text key={status} x={136 + index * 205} y={layout.recapY + 26} className="svg-small">
          {rowLabels[status].replace(/^\d\. /, '')}: {(log.totals[status] ?? 0).toFixed(2)}
        </text>
      ))}
      <text x="910" y={layout.recapY + 26} className="svg-small-bold">Total: {log.total_hours.toFixed(2)}</text>
    </g>
  )
}

function buildRemarkLayout(remarks: DailyLog['remarks']): RemarkLayout {
  const items: RemarkLayout['items'] = []
  let rowY = REMARKS_FIRST_ROW_Y

  remarks.forEach((remark, index) => {
    const detailLines = wrapSvgText(formatRemarkDetail(remark), REMARKS_DETAIL_MAX_CHARS)
    const rowHeight = Math.max(REMARKS_ROW_MIN_HEIGHT, 20 + detailLines.length * REMARKS_LINE_HEIGHT)
    items.push({
      key: `${remark.time}-${index}`,
      time: remark.time,
      status: remark.status,
      detailLines,
      y: rowY + 23,
      rowY,
      rowHeight,
      tone: remarkStatusColor(remark.status),
    })
    rowY += rowHeight + REMARKS_ITEM_GAP
  })

  const recapY = Math.max(650, rowY + 14)

  return {
    items,
    recapY,
    viewHeight: Math.max(BASE_VIEW_HEIGHT, recapY + 84),
  }
}

function formatRemarkDetail(remark: DailyLog['remarks'][number]) {
  return remark.note?.trim() || remark.location
}

function remarkStatusColor(status: string) {
  if (status === 'Driving') return colors.DRIVING
  if (status === 'On Duty (Not Driving)') return colors.ON_DUTY_NOT_DRIVING
  if (status === 'Sleeper Berth') return colors.SLEEPER_BERTH
  return colors.OFF_DUTY
}

function rowLabelLines(status: DutyStatus) {
  if (status === 'ON_DUTY_NOT_DRIVING') {
    return ['4. On Duty', '(Not Driving)']
  }

  return [rowLabels[status]]
}

function wrapSvgText(value: string, maxChars: number) {
  const words = value.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''

  words.forEach((word) => {
    if (!current) {
      current = word
      return
    }

    const next = `${current} ${word}`
    if (next.length <= maxChars) {
      current = next
      return
    }

    lines.push(current)
    current = word
  })

  if (current) {
    lines.push(current)
  }

  return lines.length > 0 ? lines : ['']
}

function Field({ x, y, width, label, value }: { x: number; y: number; width: number; label: string; value: string }) {
  return (
    <g>
      <text x={x} y={y - 8} className="svg-tiny">
        {label}
      </text>
      <rect x={x} y={y} width={width} height="30" rx="3" fill="#ffffff" stroke="#94a3b8" />
      <text x={x + 10} y={y + 20} className="svg-small-bold">
        {value}
      </text>
    </g>
  )
}

function minuteToX(minute: number) {
  return gridX + (minute / TOTAL_DAY_MINUTES) * gridW
}

function clampMinute(minute: number) {
  return Math.min(TOTAL_DAY_MINUTES, Math.max(0, minute))
}

function formatHourLabel(hour: number) {
  if (hour === 0 || hour === 24) {
    return 'Midnight'
  }

  if (hour === 12) {
    return 'Noon'
  }

  return hour > 12 ? String(hour - 12) : String(hour)
}

function formatLogDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, { dateStyle: 'full' })
}

function trim(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value
}
