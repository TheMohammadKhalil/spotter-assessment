import { FormEvent, ReactNode, useMemo, useState } from 'react'
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Fuel,
  Gauge,
  MapPinned,
  Moon,
  Navigation,
  Play,
  Route,
  ShieldCheck,
  Truck,
} from 'lucide-react'
import { planTrip } from './api'
import type { TripPlan, TripRequest } from './types'
import { DailyLogSheet } from './components/DailyLogSheet'
import { MapView } from './components/MapView'
import { StopsTimeline } from './components/StopsTimeline'
import { formatDateTime } from './utils/date'

type FormErrors = Partial<Record<keyof TripRequest, string>>

const defaultStart = new Date()
defaultStart.setHours(8, 0, 0, 0)

const initialForm: TripRequest = {
  current_location: 'Chicago, IL',
  pickup_location: 'Dallas, TX',
  dropoff_location: 'Atlanta, GA',
  current_cycle_used_hours: 12,
  start_time: toDateTimeLocal(defaultStart),
  average_speed_mph: 55,
}

function App() {
  const [form, setForm] = useState<TripRequest>(initialForm)
  const [formErrors, setFormErrors] = useState<FormErrors>({})
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const summaryItems = useMemo(() => {
    if (!plan) return []
    return [
      { label: 'Route miles', value: formatNumber(plan.summary.total_distance_miles), icon: Route, tone: '#1d4ed8' },
      { label: 'Drive hours', value: formatHours(plan.summary.estimated_drive_hours), icon: Gauge, tone: '#0f766e' },
      { label: 'Elapsed', value: formatHours(plan.summary.total_elapsed_hours), icon: Clock3, tone: '#7c3aed' },
      { label: 'Log days', value: String(plan.summary.days), icon: CalendarDays, tone: '#475569' },
      { label: 'Fuel stops', value: String(plan.summary.fuel_stops), icon: Fuel, tone: '#b45309' },
      { label: 'Restarts', value: String(plan.summary.cycle_restarts), icon: ClipboardList, tone: '#b91c1c' },
    ]
  }, [plan])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateForm(form)
    setFormErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setIsLoading(true)
    setError(null)
    setPlan(null)

    try {
      const result = await planTrip({
        ...form,
        current_cycle_used_hours: Number(form.current_cycle_used_hours),
        average_speed_mph: Number(form.average_speed_mph),
      })
      setPlan(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to plan trip.')
    } finally {
      setIsLoading(false)
    }
  }

  function updateForm<K extends keyof TripRequest>(key: K, value: TripRequest[K]) {
    setForm((current) => ({ ...current, [key]: value }))
    setFormErrors((current) => ({ ...current, [key]: undefined }))
  }

  return (
    <Box
      component="main"
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', lg: '400px minmax(0, 1fr)' },
        minHeight: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <Box
        component="aside"
        sx={{
          position: { xs: 'static', lg: 'sticky' },
          top: 0,
          height: { xs: 'auto', lg: '100vh' },
          overflowY: 'auto',
          bgcolor: 'background.paper',
          borderRight: { lg: '1px solid' },
          borderColor: 'divider',
          p: { xs: 2, sm: 2.5, md: 3 },
        }}
      >
        <Stack spacing={2.75}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box
              sx={{
                width: 44,
                height: 44,
                display: 'grid',
                placeItems: 'center',
                color: 'common.white',
                bgcolor: '#17324d',
                borderRadius: 1,
              }}
            >
              <Navigation size={22} />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h1">HOS Trip Planner</Typography>
              <Typography color="text.secondary" variant="body2">
                Route, stops, and driver logs
              </Typography>
            </Box>
          </Stack>

          <Stack component="form" onSubmit={handleSubmit} spacing={1.75} noValidate>
            <TextField
              label="Current location"
              value={form.current_location}
              onChange={(event) => updateForm('current_location', event.target.value)}
              placeholder="Chicago, IL"
              error={Boolean(formErrors.current_location)}
              helperText={formErrors.current_location ?? ' '}
              required
              fullWidth
            />
            <TextField
              label="Pickup location"
              value={form.pickup_location}
              onChange={(event) => updateForm('pickup_location', event.target.value)}
              placeholder="Dallas, TX"
              error={Boolean(formErrors.pickup_location)}
              helperText={formErrors.pickup_location ?? ' '}
              required
              fullWidth
            />
            <TextField
              label="Dropoff location"
              value={form.dropoff_location}
              onChange={(event) => updateForm('dropoff_location', event.target.value)}
              placeholder="Atlanta, GA"
              error={Boolean(formErrors.dropoff_location)}
              helperText={formErrors.dropoff_location ?? ' '}
              required
              fullWidth
            />
            <Grid container spacing={1.5}>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Cycle used"
                  type="number"
                  inputProps={{ min: 0, max: 70, step: 0.25 }}
                  value={Number.isNaN(form.current_cycle_used_hours) ? '' : form.current_cycle_used_hours}
                  onChange={(event) => updateForm('current_cycle_used_hours', parseNumberField(event.target.value))}
                  error={Boolean(formErrors.current_cycle_used_hours)}
                  helperText={formErrors.current_cycle_used_hours ?? 'Hours'}
                  required
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Avg speed"
                  type="number"
                  inputProps={{ min: 35, max: 70 }}
                  value={Number.isNaN(form.average_speed_mph) ? '' : form.average_speed_mph}
                  onChange={(event) => updateForm('average_speed_mph', parseNumberField(event.target.value))}
                  error={Boolean(formErrors.average_speed_mph)}
                  helperText={formErrors.average_speed_mph ?? 'MPH'}
                  required
                  fullWidth
                />
              </Grid>
            </Grid>
            <TextField
              label="Start time"
              type="datetime-local"
              value={form.start_time}
              onChange={(event) => updateForm('start_time', event.target.value)}
              error={Boolean(formErrors.start_time)}
              helperText={formErrors.start_time ?? ' '}
              required
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
            <Button
              type="submit"
              variant="contained"
              disabled={isLoading}
              startIcon={isLoading ? <CircularProgress size={18} color="inherit" /> : <Play size={18} />}
              sx={{ mt: 0.25 }}
            >
              {isLoading ? 'Planning route' : 'Plan trip'}
            </Button>
          </Stack>

          <RulePanel plan={plan} />
        </Stack>
      </Box>

      <Box component="section" sx={{ minWidth: 0, p: { xs: 1.5, sm: 2, md: 3 } }}>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ApiErrorState message={error} />
        ) : plan ? (
          <Stack spacing={{ xs: 1.75, md: 2.25 }}>
            <TripHeader plan={plan} />

            <Grid container spacing={1.5}>
              {summaryItems.map((item) => {
                const Icon = item.icon
                return (
                  <Grid item xs={6} md={4} xl={2} key={item.label}>
                    <MetricCard label={item.label} value={item.value} icon={<Icon size={19} />} tone={item.tone} />
                  </Grid>
                )
              })}
            </Grid>

            <Grid container rowSpacing={2} columnSpacing={{ xs: 0, sm: 2 }}>
              <Grid item xs={12} xl={8}>
                <Paper sx={{ p: { xs: 1.25, sm: 1.75, md: 2 }, height: '100%' }}>
                  <Stack spacing={1.5}>
                    <SectionHeading
                      icon={<MapPinned size={20} />}
                      title="Route map"
                      subtitle={`${formatDateTime(plan.summary.starts_at)} to ${formatDateTime(plan.summary.ends_at)}`}
                    />
                    <MapLegend />
                    <MapView plan={plan} />
                  </Stack>
                </Paper>
              </Grid>
              <Grid item xs={12} xl={4}>
                <HosStatusPanel plan={plan} />
              </Grid>
            </Grid>

            <Grid container rowSpacing={2} columnSpacing={{ xs: 0, sm: 2 }}>
              <Grid item xs={12} lg={5}>
                <StopsTimeline stops={plan.stops} />
              </Grid>
              <Grid item xs={12} lg={7}>
                <RouteInstructions plan={plan} />
              </Grid>
            </Grid>

            <Stack spacing={1.5}>
              <SectionHeading
                icon={<ClipboardList size={20} />}
                title="Driver daily logs"
                subtitle="Generated from the same duty-status timeline as the route stops and summary."
              />
              <Stack spacing={2}>
                {plan.daily_logs.map((log) => (
                  <DailyLogSheet key={log.date} log={log} />
                ))}
              </Stack>
            </Stack>
          </Stack>
        ) : (
          <EmptyState />
        )}
      </Box>
    </Box>
  )
}

function TripHeader({ plan }: { plan: TripPlan }) {
  return (
    <Paper sx={{ p: { xs: 1.75, md: 2.25 } }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
        spacing={1.5}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="caption" color="text.secondary" fontWeight={900} sx={{ textTransform: 'uppercase', letterSpacing: 1 }}>
            Planned trip
          </Typography>
          <Typography variant="h1" sx={{ mt: 0.25 }}>
            {String(plan.inputs.current_location)} to {String(plan.inputs.dropoff_location)}
          </Typography>
          <Typography color="text.secondary" variant="body2" sx={{ mt: 0.5 }}>
            Pickup: {String(plan.inputs.pickup_location)} · {formatNumber(plan.summary.total_distance_miles)} miles
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Chip icon={<ShieldCheck size={16} />} label="70/8 cycle" color="primary" variant="outlined" />
          <Chip icon={<CheckCircle2 size={16} />} label="Canonical timeline" color="success" variant="outlined" />
        </Stack>
      </Stack>
    </Paper>
  )
}

function MetricCard({ label, value, icon, tone }: { label: string; value: string; icon: ReactNode; tone: string }) {
  return (
    <Card sx={{ height: '100%', position: 'relative', overflow: 'hidden' }}>
      <Box sx={{ position: 'absolute', inset: '0 auto 0 0', width: 4, bgcolor: tone }} />
      <CardContent sx={{ p: { xs: 1.5, sm: 1.75 }, '&:last-child': { pb: { xs: 1.5, sm: 1.75 } } }}>
        <Stack spacing={1}>
          <Box
            sx={{
              width: 34,
              height: 34,
              display: 'grid',
              placeItems: 'center',
              borderRadius: 1,
              color: tone,
              bgcolor: `${tone}14`,
            }}
          >
            {icon}
          </Box>
          <Box>
            <Typography color="text.secondary" variant="caption" fontWeight={900} sx={{ textTransform: 'uppercase', letterSpacing: 0.6 }}>
              {label}
            </Typography>
            <Typography sx={{ fontSize: { xs: '1.3rem', sm: '1.55rem' }, fontWeight: 950, lineHeight: 1.05 }}>
              {value}
            </Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}

function HosStatusPanel({ plan }: { plan: TripPlan }) {
  const dutyItems = [
    { label: 'Initial cycle available', value: formatHours(plan.summary.initial_cycle_available_hours), icon: ShieldCheck },
    { label: 'On duty', value: formatHours(plan.summary.on_duty_hours), icon: Truck },
    { label: 'Off duty', value: formatHours(plan.summary.off_duty_hours), icon: Moon },
    { label: '10-hour rests', value: String(plan.summary.ten_hour_rests), icon: Clock3 },
  ]

  return (
    <Paper sx={{ p: { xs: 1.75, md: 2 }, height: '100%' }}>
      <Stack spacing={1.75}>
        <SectionHeading icon={<ShieldCheck size={20} />} title="HOS status" subtitle="Rule checks reflected in the timeline." />
        <Grid container spacing={1}>
          {dutyItems.map((item) => {
            const Icon = item.icon
            return (
              <Grid item xs={6} key={item.label}>
                <Box sx={{ p: 1.25, border: '1px solid', borderColor: 'divider', borderRadius: 1, bgcolor: '#f8fafc' }}>
                  <Stack spacing={0.75}>
                    <Box sx={{ color: 'primary.main' }}>
                      <Icon size={17} />
                    </Box>
                    <Typography color="text.secondary" variant="caption" fontWeight={850}>
                      {item.label}
                    </Typography>
                    <Typography fontWeight={950}>{item.value}</Typography>
                  </Stack>
                </Box>
              </Grid>
            )
          })}
        </Grid>
        <Divider />
        <Stack spacing={1.2}>
          {plan.hos_explanations.map((item) => (
            <Box key={item.title}>
              <Typography variant="h3" sx={{ mb: 0.35 }}>
                {item.title}
              </Typography>
              <Typography color="text.secondary" variant="body2">
                {item.body}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Stack>
    </Paper>
  )
}

function RulePanel({ plan }: { plan: TripPlan | null }) {
  return (
    <Paper sx={{ p: 1.75, bgcolor: '#f8fafc' }}>
      <Stack spacing={1.25}>
        <Stack direction="row" spacing={1} alignItems="center">
          <ShieldCheck size={18} color="#1d4ed8" />
          <Typography variant="h3">Assessment rule set</Typography>
        </Stack>
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
          <Chip size="small" label="11-hour drive" />
          <Chip size="small" label="14-hour window" />
          <Chip size="small" label="8-hour break" />
          <Chip size="small" label="70/8 cycle" />
        </Stack>
        {plan && (
          <Box sx={{ pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
            <Typography color="text.secondary" variant="caption" fontWeight={850}>
              Cycle available at dispatch
            </Typography>
            <Typography fontWeight={950}>{formatHours(plan.summary.initial_cycle_available_hours)}</Typography>
          </Box>
        )}
      </Stack>
    </Paper>
  )
}

function RouteInstructions({ plan }: { plan: TripPlan }) {
  return (
    <Paper sx={{ height: '100%' }}>
      <Stack spacing={1.25} sx={{ p: { xs: 1.5, md: 1.75 } }}>
        <SectionHeading icon={<Route size={20} />} title="Route instructions" />
        <Stack divider={<Divider flexItem />}>
          {plan.route.instructions.length === 0 && (
            <Typography color="text.secondary" sx={{ py: 1.5 }}>
              No turn-by-turn instructions were returned; the route line and scheduled stops are available.
            </Typography>
          )}
          {plan.route.instructions.slice(0, 16).map((instruction, index) => (
            <Stack direction="row" spacing={1.25} key={`${instruction.text}-${index}`} sx={{ py: 1.15 }}>
              <Box
                sx={{
                  width: 25,
                  height: 25,
                  display: 'grid',
                  flex: '0 0 25px',
                  placeItems: 'center',
                  borderRadius: '50%',
                  bgcolor: 'primary.light',
                  color: 'primary.dark',
                  fontSize: '0.76rem',
                  fontWeight: 950,
                }}
              >
                {index + 1}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 700, overflowWrap: 'anywhere' }}>
                  {instruction.text}
                </Typography>
                <Typography color="text.secondary" variant="caption" sx={{ overflowWrap: 'anywhere' }}>
                  {instruction.distance_miles} mi · {Math.round(instruction.duration_minutes)} min
                </Typography>
              </Box>
            </Stack>
          ))}
        </Stack>
      </Stack>
    </Paper>
  )
}

function MapLegend() {
  return (
    <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
      <LegendDot color="#111827" label="Current" />
      <LegendDot color="#2563eb" label="Pickup" />
      <LegendDot color="#16a34a" label="Dropoff" />
      <LegendDot color="#ca8a04" label="Fuel" />
      <LegendDot color="#0891b2" label="Break" />
      <LegendDot color="#7c3aed" label="Rest" />
    </Stack>
  )
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <Stack direction="row" alignItems="center" spacing={0.6} sx={{ px: 0.85, py: 0.45, border: '1px solid', borderColor: 'divider', borderRadius: 1, bgcolor: '#fff' }}>
      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color }} />
      <Typography variant="caption" color="text.secondary" fontWeight={850}>
        {label}
      </Typography>
    </Stack>
  )
}

function LoadingState() {
  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, maxWidth: 860, mx: 'auto', mt: { xs: 0, md: 6 } }}>
      <Stack spacing={2}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box sx={{ width: 42, height: 42, display: 'grid', placeItems: 'center', borderRadius: 1, bgcolor: 'primary.light', color: 'primary.dark' }}>
            <Truck size={22} />
          </Box>
          <Box>
            <Typography variant="h2">Building compliant trip plan</Typography>
            <Typography color="text.secondary" variant="body2">
              Resolving route geometry and scheduling duty events.
            </Typography>
          </Box>
        </Stack>
        <LinearProgress />
        <Grid container rowSpacing={1.25} columnSpacing={{ xs: 0, sm: 1.25 }}>
          {[0, 1, 2].map((item) => (
            <Grid item xs={12} sm={4} key={item}>
              <Box sx={{ height: 86, borderRadius: 1, bgcolor: '#f1f5f9', border: '1px solid #e2e8f0' }} />
            </Grid>
          ))}
        </Grid>
      </Stack>
    </Paper>
  )
}

function EmptyState() {
  return (
    <Paper sx={{ p: { xs: 2.25, md: 4 }, minHeight: { xs: 360, md: 480 }, display: 'grid', placeItems: 'center' }}>
      <Stack alignItems="center" spacing={1.5} sx={{ textAlign: 'center', maxWidth: 560 }}>
        <Box sx={{ width: 58, height: 58, display: 'grid', placeItems: 'center', borderRadius: 1.5, bgcolor: '#e0f2fe', color: '#075985' }}>
          <MapPinned size={30} />
        </Box>
        <Typography variant="h1">Ready for dispatch planning</Typography>
        <Typography color="text.secondary">
          Enter trip locations and current cycle usage to generate the route, required stops, and daily log sheets.
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center" sx={{ pt: 0.5 }}>
          <Chip size="small" label="Route map" />
          <Chip size="small" label="HOS timeline" />
          <Chip size="small" label="Daily logs" />
        </Stack>
      </Stack>
    </Paper>
  )
}

function ApiErrorState({ message }: { message: string }) {
  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, maxWidth: 860, mx: 'auto', mt: { xs: 0, md: 6 } }}>
      <Alert severity="error" icon={<AlertTriangle size={22} />}>
        <AlertTitle>Unable to plan this trip</AlertTitle>
        {message}
      </Alert>
    </Paper>
  )
}

function SectionHeading({ icon, title, subtitle }: { icon: ReactNode; title: string; subtitle?: string }) {
  return (
    <Stack direction="row" spacing={1.1} alignItems="center" sx={{ minWidth: 0 }}>
      <Box sx={{ color: 'primary.main', display: 'grid', placeItems: 'center', flex: '0 0 auto' }}>{icon}</Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h2">{title}</Typography>
        {subtitle && (
          <Typography color="text.secondary" variant="body2" noWrap={false}>
            {subtitle}
          </Typography>
        )}
      </Box>
    </Stack>
  )
}

function validateForm(values: TripRequest): FormErrors {
  const errors: FormErrors = {}
  if (!values.current_location.trim()) errors.current_location = 'Current location is required.'
  if (!values.pickup_location.trim()) errors.pickup_location = 'Pickup location is required.'
  if (!values.dropoff_location.trim()) errors.dropoff_location = 'Dropoff location is required.'
  if (Number.isNaN(values.current_cycle_used_hours) || values.current_cycle_used_hours < 0 || values.current_cycle_used_hours > 70) {
    errors.current_cycle_used_hours = 'Enter 0 to 70 hours.'
  }
  if (Number.isNaN(values.average_speed_mph) || values.average_speed_mph < 35 || values.average_speed_mph > 70) {
    errors.average_speed_mph = 'Enter 35 to 70 mph.'
  }
  if (!values.start_time) errors.start_time = 'Start time is required.'
  return errors
}

function parseNumberField(value: string) {
  return value === '' ? Number.NaN : Number(value)
}

function toDateTimeLocal(date: Date) {
  const offset = date.getTimezoneOffset()
  const localDate = new Date(date.getTime() - offset * 60_000)
  return localDate.toISOString().slice(0, 16)
}

function formatHours(value: number) {
  return `${Number(value).toFixed(value % 1 === 0 ? 0 : 1)}h`
}

function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)
}

export default App
