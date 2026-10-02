import { Box, Chip, Divider, Paper, Stack, Typography } from '@mui/material'
import { Coffee, Fuel, Moon, PackageCheck, PackageOpen, RotateCcw } from 'lucide-react'
import type { TripStop } from '../types'
import { formatDateTime } from '../utils/date'

const stopMeta = {
  pickup: { icon: PackageOpen, label: 'Pickup', color: '#2563eb', bg: '#dbeafe' },
  dropoff: { icon: PackageCheck, label: 'Dropoff', color: '#15803d', bg: '#dcfce7' },
  fuel: { icon: Fuel, label: 'Fuel', color: '#b45309', bg: '#fef3c7' },
  break: { icon: Coffee, label: 'Break', color: '#0891b2', bg: '#cffafe' },
  rest: { icon: Moon, label: '10h Rest', color: '#7c3aed', bg: '#ede9fe' },
  restart: { icon: RotateCcw, label: '34h Restart', color: '#b91c1c', bg: '#fee2e2' },
}

type Props = {
  stops: TripStop[]
}

export function StopsTimeline({ stops }: Props) {
  return (
    <Paper sx={{ height: '100%' }}>
      <Stack spacing={1.25} sx={{ p: { xs: 1.5, md: 1.75 } }}>
        <Stack direction="row" spacing={1.1} alignItems="center">
          <Box sx={{ color: 'primary.main', display: 'grid', placeItems: 'center' }}>
            <PackageCheck size={20} />
          </Box>
          <Box>
            <Typography variant="h2">Scheduled stops</Typography>
            <Typography color="text.secondary" variant="body2">
              {stops.length} timeline events requiring location context
            </Typography>
          </Box>
        </Stack>
        <Stack divider={<Divider flexItem />} sx={{ position: 'relative' }}>
          {stops.map((stop) => {
            const meta = stopMeta[stop.type as keyof typeof stopMeta] ?? stopMeta.break
            const Icon = meta.icon
            return (
              <Stack direction="row" spacing={1.35} key={stop.id} sx={{ py: 1.35, minWidth: 0 }}>
                <Box sx={{ position: 'relative', flex: '0 0 36px', display: 'grid', justifyItems: 'center' }}>
                  <Box
                    sx={{
                      width: 34,
                      height: 34,
                      display: 'grid',
                      placeItems: 'center',
                      color: meta.color,
                      bgcolor: meta.bg,
                      border: `1px solid ${meta.color}44`,
                      borderRadius: 1,
                      zIndex: 1,
                    }}
                  >
                    <Icon size={17} />
                  </Box>
                </Box>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ minWidth: 0 }}>
                    <Typography fontWeight={900} noWrap>
                      {meta.label}
                    </Typography>
                    <Chip
                      size="small"
                      label={`${Math.round(stop.duration_minutes)} min`}
                      sx={{ bgcolor: '#f8fafc', flex: '0 0 auto' }}
                    />
                  </Stack>
                  <Typography color="text.secondary" variant="body2" sx={{ mt: 0.35, lineHeight: 1.45 }}>
                    {stop.description}
                  </Typography>
                  <Typography color="text.secondary" variant="caption" sx={{ display: 'block', mt: 0.75 }}>
                    {formatDateTime(stop.start_time)} · {trim(stop.location.name, 34)} · {stop.distance_miles} mi
                  </Typography>
                </Box>
              </Stack>
            )
          })}
        </Stack>
      </Stack>
    </Paper>
  )
}

function trim(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value
}
