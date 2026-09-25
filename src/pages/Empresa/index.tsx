import { useState } from 'react'
import {
  ShieldCheck,
  TrendingUp,
  DollarSign,
  ListChecks,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  Info,
  Users,
  Scale,
  FileText,
  MessageSquare,
} from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { cn } from '@/lib/utils'

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = 'prioridades' | 'legal' | 'mercado' | 'presupuesto'

interface AccordionItem {
  title: string
  icon: React.ReactNode
  badge?: string
  badgeColor?: string
  children: React.ReactNode
}

// ─── Small helpers ─────────────────────────────────────────────────────────────

function Accordion({ title, icon, badge, badgeColor = 'bg-vygo-green/10 text-vygo-green', children }: AccordionItem) {
  const [open, setOpen] = useState(false)
  return (
    <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-3 w-full px-4 py-3.5 text-left hover:bg-vygo-card-2 transition-colors"
      >
        <div className="w-8 h-8 rounded-xl bg-vygo-card-2 flex items-center justify-center flex-shrink-0">
          {icon}
        </div>
        <span className="flex-1 text-sm font-semibold text-vygo-white">{title}</span>
        {badge && (
          <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-full mr-1', badgeColor)}>{badge}</span>
        )}
        {open ? <ChevronUp size={16} className="text-vygo-secondary" /> : <ChevronDown size={16} className="text-vygo-secondary" />}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-vygo-border text-sm text-vygo-secondary space-y-2 animate-fade-in">
          {children}
        </div>
      )}
    </div>
  )
}

function InfoBox({ type, children }: { type: 'warning' | 'info' | 'success'; children: React.ReactNode }) {
  const styles = {
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
    success: 'bg-green-50 border-green-200 text-green-800',
  }
  const icons = {
    warning: <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />,
    info: <Info size={14} className="flex-shrink-0 mt-0.5" />,
    success: <CheckCircle2 size={14} className="flex-shrink-0 mt-0.5" />,
  }
  return (
    <div className={cn('flex gap-2 border rounded-xl p-3 text-xs leading-relaxed', styles[type])}>
      {icons[type]}
      <div>{children}</div>
    </div>
  )
}

function Row({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-vygo-border last:border-0">
      <span className="text-vygo-secondary text-xs leading-snug">{label}</span>
      <div className="text-right">
        <span className="text-vygo-white text-xs font-semibold">{value}</span>
        {sub && <p className="text-[10px] text-vygo-secondary mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function Q({ n, text }: { n: number; text: string }) {
  return (
    <div className="flex gap-2 py-2 border-b border-vygo-border last:border-0">
      <span className="w-5 h-5 rounded-full bg-vygo-green text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
        {n}
      </span>
      <p className="text-vygo-white text-xs leading-relaxed">{text}</p>
    </div>
  )
}

// ─── Tabs ──────────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'prioridades', label: 'Prioridades', icon: <ListChecks size={14} /> },
  { id: 'legal',       label: 'Legal',       icon: <Scale size={14} /> },
  { id: 'mercado',     label: 'Mercado',     icon: <Users size={14} /> },
  { id: 'presupuesto', label: 'Presupuesto', icon: <DollarSign size={14} /> },
]

// ─── Tab content ───────────────────────────────────────────────────────────────

function TabPrioridades() {
  const items = [
    {
      n: 1,
      title: 'Identificar quién creó qué',
      detail: 'Listar a todos los que aportaron código, diseño, modelo, nombre o datos durante y después de HackMTY. Revisar reglas de propiedad del evento. Definir qué puede aportar cada quien a la empresa.',
      urgency: 'AHORA',
    },
    {
      n: 2,
      title: 'Acuerdo entre fundadores',
      detail: 'Porcentajes, funciones, decisiones, qué pasa si alguien se va, vesting (adquisición gradual), cesión de propiedad intelectual a la empresa, confidencialidad y resolución de bloqueos. No repartiría 20% a cada uno por inercia; la participación debe reflejar aportación y permanencia.',
      urgency: 'AHORA',
    },
    {
      n: 3,
      title: 'Probar el acceso a datos en teléfonos reales',
      detail: 'Demostrar que el mecanismo de lectura de notificaciones funciona en producción. Sin esto, no hay producto. Documentar qué pasa cuando Rappi, Uber o DiDi cambian el formato de sus notificaciones.',
      urgency: 'ESTA SEMANA',
    },
    {
      n: 4,
      title: 'Entrevistas y piloto medible',
      detail: '25–30 repartidores de Monterrey. Medir ganancia neta por hora antes y después. El piloto define si hay negocio o no. Ver pestaña Mercado para las preguntas.',
      urgency: 'ESTA SEMANA',
    },
    {
      n: 5,
      title: 'Constituir la empresa y abrir cuenta bancaria',
      detail: 'Sólo después de resolver propiedad intelectual y acuerdo de fundadores. Opciones: S.A.P.I. de C.V. (mejor para inversión), S.A. de C.V. o S.A.S. (con limitaciones). Ver pestaña Legal.',
      urgency: 'ANTES DE INVERSIÓN',
    },
    {
      n: 6,
      title: 'Negociar la inversión por escrito',
      detail: '"Tenemos potenciales inversionistas" no es dinero. Revisar monto, valuación, porcentaje, derechos de voto y veto, diluciones futuras, preferencias al vender y qué pasa si no cumplen metas. Pedir primero una hoja de términos.',
      urgency: 'ANTES DE FIRMAR',
    },
  ]

  const colors: Record<string, string> = {
    'AHORA':           'bg-red-100 text-red-700',
    'ESTA SEMANA':     'bg-amber-100 text-amber-700',
    'ANTES DE INVERSIÓN': 'bg-blue-100 text-blue-700',
    'ANTES DE FIRMAR': 'bg-purple-100 text-purple-700',
  }

  return (
    <div className="space-y-3">
      {/* ── Deal activo ───────────────────────────────────────────────── */}
      <div className="bg-vygo-green/5 border border-vygo-green/30 rounded-2xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <DollarSign size={16} className="text-vygo-green flex-shrink-0" />
          <p className="text-sm font-bold text-vygo-white">Oferta de inversión activa — análisis</p>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="bg-white/60 rounded-xl p-2.5 text-center">
            <p className="text-[11px] text-vygo-secondary">Inversión</p>
            <p className="text-base font-bold text-vygo-white">$400k</p>
            <p className="text-[10px] text-vygo-secondary">MXN</p>
          </div>
          <div className="bg-white/60 rounded-xl p-2.5 text-center">
            <p className="text-[11px] text-vygo-secondary">Equity ofrecido</p>
            <p className="text-base font-bold text-vygo-white">20%</p>
            <p className="text-[10px] text-vygo-secondary">propuesto</p>
          </div>
          <div className="bg-white/60 rounded-xl p-2.5 text-center">
            <p className="text-[11px] text-vygo-secondary">Val. post-money</p>
            <p className="text-base font-bold text-vygo-white">$2M</p>
            <p className="text-[10px] text-vygo-secondary">MXN (~$114k USD)</p>
          </div>
        </div>

        <div className="space-y-1.5 text-xs">
          <div className="flex justify-between py-1 border-b border-vygo-border">
            <span className="text-vygo-secondary">Valuación pre-money implícita</span>
            <span className="font-semibold text-vygo-white">$1,600,000 MXN</span>
          </div>
          <div className="flex justify-between py-1 border-b border-vygo-border">
            <span className="text-vygo-secondary">Equity que retienen los fundadores</span>
            <span className="font-semibold text-vygo-white">80% (16% c/u si son 5 iguales)</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-vygo-secondary">Rango estándar pre-seed México</span>
            <span className="font-semibold text-amber-700">5% – 15%</span>
          </div>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800 leading-relaxed">
          <strong>20% es negociable.</strong> El estándar para una ronda angel pre-revenue en México es 5–15%. Ceder 20% ahora deja poco margen para futuras rondas sin perder control. Dos opciones a negociar: reducir a 15% por el mismo monto ($400k = 15% implica valuación post-money de ~$2.67M MXN), o mantener el 20% y solicitar un monto mayor (~$600k MXN).
        </div>
      </div>

      <InfoBox type="warning">
        Antes de cerrar el deal, deben demostrar que el mecanismo de lectura de datos funciona en producción y que VYGO mejora la ganancia neta real del repartidor. Esos son los dos riesgos que pueden tumbar la valuación aunque los términos estén bien redactados.
      </InfoBox>

      {items.map((item) => (
        <div key={item.n} className="bg-vygo-card border border-vygo-border rounded-2xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-vygo-green flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-white text-xs font-bold">{item.n}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <p className="text-sm font-semibold text-vygo-white">{item.title}</p>
                <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full', colors[item.urgency])}>
                  {item.urgency}
                </span>
              </div>
              <p className="text-xs text-vygo-secondary leading-relaxed">{item.detail}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function TabLegal() {
  return (
    <div className="space-y-3">
      <InfoBox type="info">
        Esto es una hoja de trabajo para llevar con abogado corporativo y contador. Los documentos finales y el tratamiento fiscal dependen de quiénes serán socios y de cómo cobrarán.
      </InfoBox>

      <Accordion title="Tipo de sociedad" icon={<Scale size={16} className="text-vygo-secondary" />} badge="Decidir primero" badgeColor="bg-blue-100 text-blue-700">
        <div className="space-y-3">
          <div className="space-y-2">
            <p className="font-semibold text-vygo-white text-xs">S.A.P.I. de C.V.</p>
            <p>Permite distintas clases de acciones y condiciones, ideal para inversión. Más herramientas societarias. Pedir cotización al abogado.</p>
          </div>
          <div className="space-y-2">
            <p className="font-semibold text-vygo-white text-xs">S.A. de C.V.</p>
            <p>Opción clásica. Pedir cotización y comparar estatutos con S.A.P.I.</p>
          </div>
          <div className="space-y-2">
            <p className="font-semibold text-vygo-white text-xs">S.A.S. — no recomendada si la inversión es próxima</p>
            <p>Constitución electrónica más sencilla, pero tiene restricciones y límite de ingresos de $7.6M MXN anuales (~2026). No elegirla solo porque el trámite inicial parece más fácil.</p>
          </div>
        </div>
      </Accordion>

      <Accordion title="Constitución y administración" icon={<FileText size={16} className="text-vygo-secondary" />}>
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Denominación social (buscar "VYGO" en IMPI antes de usarla oficialmente)</li>
          <li>Estatutos con cláusulas de vesting, salidas y propiedad intelectual</li>
          <li>Definir accionistas, porcentajes y poderes del administrador</li>
          <li>Libros corporativos</li>
          <li>Cuenta bancaria empresarial (no mezclar con cuentas personales)</li>
          <li>Reglas escritas para aprobar gastos y acceso a repositorios/dominios</li>
          <li>Registrar beneficiario controlador</li>
        </ul>
      </Accordion>

      <Accordion title="Impuestos y contabilidad" icon={<TrendingUp size={16} className="text-vygo-secondary" />}>
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Inscripción en RFC de la persona moral, definir régimen y actividades</li>
          <li>ISR personas morales: 30% sobre resultado fiscal (no sobre ingresos brutos)</li>
          <li>Emisión de CFDI, cómo cobrarán suscripciones</li>
          <li>Registro de aportaciones de socios y pagos a proveedores extranjeros</li>
          <li>IVA, acreditamientos, retenciones — confirmar con contador</li>
          <li>Declaraciones mensuales al SAT</li>
          <li>Conciliación mensual: banco + pasarela + facturas</li>
        </ul>
        <InfoBox type="warning">
          El SAT espera que los servicios comprados al extranjero (AWS, Google, Claude) tengan tratamiento fiscal específico. Su contador debe definirlo antes de la primera factura.
        </InfoBox>
      </Accordion>

      <Accordion title="Marca y propiedad intelectual" icon={<ShieldCheck size={16} className="text-vygo-secondary" />}>
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Buscar "VYGO" y variantes en IMPI <strong className="text-vygo-white">antes</strong> de invertir en publicidad</li>
          <li>Revisar disponibilidad de dominio y usuarios de redes sociales</li>
          <li>Solicitar registro de marca por las clases correspondientes</li>
          <li>Referencia de tarifa IMPI: $2,695 MXN + IVA por solicitud en línea — confirmar monto al generar línea de captura</li>
          <li>Repositorios, dominio y contratos de desarrollo bajo titularidad deliberada (la empresa, no una persona)</li>
          <li>Código creado durante HackMTY: revisar reglas de propiedad del evento antes de constituir</li>
        </ul>
      </Accordion>

      <Accordion title="Privacidad y datos" icon={<ShieldCheck size={16} className="text-vygo-secondary" />} badge="Crítico" badgeColor="bg-red-100 text-red-700">
        <p className="mb-2">Ley aplicable: Ley Federal de Protección de Datos Personales en Posesión de los Particulares (México).</p>
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Inventario de datos: ubicación, historial de turnos, pedidos, ingresos estimados, identificadores de dispositivo, contenido de notificaciones</li>
          <li>Qué se guarda, por cuánto tiempo y quién accede</li>
          <li>Qué proveedores reciben datos (AWS, Google, Anthropic)</li>
          <li>Cómo se atienden derechos de usuarios (acceso, rectificación, cancelación, oposición)</li>
          <li>Proceso para borrar una cuenta y sus datos</li>
          <li>Aviso de privacidad debe describir el funcionamiento real, no uno hipotético</li>
        </ul>
        <InfoBox type="warning">
          Que un repartidor autorice leer sus notificaciones no equivale a tener una alianza con Uber, Rappi o DiDi. Revisar los términos de cada plataforma y las políticas de Google Play por separado. Google Play trata ubicación y datos del dispositivo como sensibles y exige divulgación y consentimiento explícito.
        </InfoBox>
      </Accordion>

      <Accordion title="Contratos necesarios" icon={<FileText size={16} className="text-vygo-secondary" />}>
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Acuerdo de fundadores (antes que todo)</li>
          <li>Términos de uso para repartidores (estimaciones, errores, disponibilidad, cancelación)</li>
          <li>Política de privacidad</li>
          <li>Contratos con desarrolladores y colaboradores externos</li>
          <li>Revisión de condiciones de Google Maps, AWS, Anthropic y cualquier SDK</li>
          <li>Si contratan personal: validar si es relación laboral (obligaciones IMSS) o prestación de servicios — caso por caso con asesor laboral</li>
        </ul>
      </Accordion>

      <Accordion title="Acuerdo con inversionistas — $400k MXN / 20%" icon={<DollarSign size={16} className="text-vygo-secondary" />} badge="No firmar sin revisar" badgeColor="bg-red-100 text-red-700">
        <p className="mb-3">Solicitar primero una hoja de términos (term sheet) por escrito antes de cualquier negociación verbal. Verificar punto por punto:</p>

        <p className="text-[11px] font-semibold text-vygo-white uppercase tracking-wide mb-2">Estructura básica del deal</p>
        <ul className="space-y-1.5 list-disc list-inside mb-3">
          <li>Confirmar que los $400k MXN entran a la tesorería de <strong className="text-vygo-white">la empresa</strong>, no a cuentas personales de fundadores</li>
          <li>Negociar equity a 15% — misma inversión implica valuación post-money de $2.67M MXN, más favorable para futuras rondas</li>
          <li>Solicitar desembolso por tramos ligados a milestones (ej. 50% al firmar, 50% al alcanzar X usuarios activos)</li>
        </ul>

        <p className="text-[11px] font-semibold text-vygo-white uppercase tracking-wide mb-2">Derechos del inversionista — qué es aceptable</p>
        <ul className="space-y-1.5 list-disc list-inside mb-3">
          <li>Preferencia de liquidación 1× no participante (estándar justo)</li>
          <li>Derecho de primera oferta en futuras rondas (pro-rata)</li>
          <li>Derechos de información: estados financieros trimestrales</li>
          <li>Seat de observador en consejo — no seat con voto</li>
        </ul>

        <p className="text-[11px] font-semibold text-vygo-white uppercase tracking-wide mb-2">Cláusulas a rechazar o acotar</p>
        <ul className="space-y-1.5 list-disc list-inside mb-3">
          <li>Anti-dilución ratchet completo — solo aceptar promedio ponderado base amplia</li>
          <li>Veto sobre decisiones operativas (contrataciones, gastos, estrategia de producto)</li>
          <li>Drag-along sin umbral mínimo de aprobación de fundadores</li>
          <li>Cláusula de exclusividad con el inversionista por más de 30 días</li>
        </ul>

        <p className="text-[11px] font-semibold text-vygo-white uppercase tracking-wide mb-2">Proyección de dilución</p>
        <div className="bg-vygo-card-2 rounded-xl p-3 font-mono text-[11px] text-vygo-white space-y-1">
          <p>Hoy (pre-inversión):     fundadores 100%</p>
          <p>Post $400k / 20%:        fundadores 80%  · inv. 20%</p>
          <p>Ronda A hipotética 25%:  fundadores 60%  · inv.A 25% · inv. 20%→15%</p>
          <p>Ronda B hipotética 20%:  fundadores 48%  · ...</p>
        </div>
        <p className="text-[11px] text-vygo-secondary mt-2">Con 20% cedido en la primera ronda, los fundadores quedan por debajo del 50% colectivo antes de completar una Ronda B. Con 15% inicial mantienen margen significativo más tiempo.</p>

        <InfoBox type="warning">
          No firmar ningún documento vinculante antes de que el abogado corporativo revise los términos completos, no solo el resumen.
        </InfoBox>
      </Accordion>
    </div>
  )
}

function TabMercado() {
  return (
    <div className="space-y-3">
      <InfoBox type="success">
        Meta: 25–30 entrevistas con repartidores de Monterrey. Mezclar: una sola app y varias; moto, auto y bicicleta; turnos y zonas distintas. Reclutar fuera del círculo de conocidos.
      </InfoBox>

      <InfoBox type="warning">
        No muestren VYGO al principio. Primero escuchen. Una respuesta "sí la usaría" vale poco — importan los episodios concretos, los datos que ya registran y si aceptan participar en un piloto.
      </InfoBox>

      <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-vygo-border">
          <div className="w-8 h-8 rounded-xl bg-vygo-card-2 flex items-center justify-center">
            <MessageSquare size={16} className="text-vygo-secondary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-vygo-white">Preguntas de entrevista</p>
            <p className="text-xs text-vygo-secondary">Primero contexto, luego problema, al final propuesta</p>
          </div>
        </div>
        <div className="px-4 py-3">
          <p className="text-[11px] font-semibold text-vygo-secondary uppercase tracking-wide mb-2">Contexto y última jornada</p>
          <Q n={1} text="¿Con qué plataformas trabajaste la semana pasada y cuántas horas estuviste conectado?" />
          <Q n={2} text="Cuéntame tu último turno, desde que empezaste hasta que terminaste." />

          <p className="text-[11px] font-semibold text-vygo-secondary uppercase tracking-wide mt-4 mb-2">Decisiones y datos</p>
          <Q n={3} text="En tu última oferta que rechazaste, ¿qué viste y por qué la rechazaste?" />
          <Q n={4} text="¿Cuándo aceptaste un pedido que después resultó malo? ¿Qué dato te faltó?" />
          <Q n={5} text="¿Cómo calculas hoy si te conviene un pedido? Muéstrame tu método, si tienes uno." />

          <p className="text-[11px] font-semibold text-vygo-secondary uppercase tracking-wide mt-4 mb-2">Costos y tiempos reales</p>
          <Q n={6} text="¿Cuánto gastaste en gasolina, comisiones, estacionamiento y mantenimiento la semana pasada? ¿Cómo lo sabes?" />
          <Q n={7} text="¿Qué tanto tiempo esperas en restaurantes y cómo afecta tus decisiones?" />
          <Q n={8} text="¿Qué haces cuando llegan ofertas de dos apps casi al mismo tiempo?" />

          <p className="text-[11px] font-semibold text-vygo-secondary uppercase tracking-wide mt-4 mb-2">Herramientas actuales y fricción</p>
          <Q n={9} text="¿Usas alguna app, hoja de cálculo o grupo para decidir o registrar ganancias? ¿Qué te cuesta usarla?" />
          <Q n={10} text="¿En qué momento consultarías otra pantalla y en cuál sería peligroso o imposible?" />

          <p className="text-[11px] font-semibold text-vygo-secondary uppercase tracking-wide mt-4 mb-2">Privacidad y disposición a pagar</p>
          <Q n={11} text="¿Qué información aceptarías compartir para recibir recomendaciones? ¿Cuál no?" />
          <Q n={12} text="¿Qué tendría que pasar durante una semana para que dijeras «esto me ayudó»?" />
          <Q n={13} text="¿Has pagado por alguna herramienta para trabajar? ¿Cuál y cuánto?" />
          <Q n={14} text="[Mostrar VYGO] ¿Puedes interpretar esta recomendación en 5 segundos? ¿Qué cambiarías? Si comprobara una mejora verificable, ¿cómo preferirías pagarla? (pedir precio concreto, no rango)" />
        </div>
      </div>

      <Accordion title="Métricas del piloto" icon={<TrendingUp size={16} className="text-vygo-secondary" />}>
        <p className="mb-2">Definir antes de empezar el piloto, no después de ver los resultados:</p>
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Ganancia neta por hora trabajada (después de gasolina, comisiones y esperas)</li>
          <li>Costo por kilómetro recorrido</li>
          <li>Pedidos aceptados / rechazados y resultado de cada uno</li>
          <li>Tiempo promedio de espera en restaurantes</li>
          <li>Errores de lectura de notificaciones</li>
          <li>Retención semanal (¿siguen usando VYGO en semana 2 y 3?)</li>
          <li>% de recomendaciones que el repartidor siguió</li>
        </ul>
        <InfoBox type="info">
          Comparar jornadas suficientemente parecidas de los <strong>mismos</strong> repartidores. Documentar día, clima y zona. La mejora tiene que superar el costo de la suscripción y la fricción de usar otra app.
        </InfoBox>
      </Accordion>

      <Accordion title="Lo que invalida el estudio" icon={<AlertTriangle size={16} className="text-vygo-secondary" />} badge="Evitar" badgeColor="bg-red-100 text-red-700">
        <ul className="space-y-1.5 list-disc list-inside">
          <li>Entrevistar solo a amigos o conocidos que quieren ayudarte</li>
          <li>Pedir contraseñas o capturas que muestren datos de clientes de las plataformas</li>
          <li>Mostrar VYGO antes de entender el problema actual del repartidor</li>
          <li>Preguntar "¿cuánto pagarías?" antes de describir el beneficio concreto</li>
          <li>Interpretar "sí me interesa" como intención real de compra</li>
        </ul>
      </Accordion>
    </div>
  )
}

function TabPresupuesto() {
  return (
    <div className="space-y-3">
      <InfoBox type="warning">
        Estos precios son referencias públicas en USD (sept 2025). No hay un tipo de cambio fijo. Verifiquen cada precio en México antes de presupuestar. "Tenemos potenciales inversionistas" no es capital disponible para gastar hoy.
      </InfoBox>

      <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden">
        <div className="px-4 py-3 border-b border-vygo-border">
          <p className="text-sm font-semibold text-vygo-white">Herramientas del equipo / mes</p>
        </div>
        <div className="px-4 py-2">
          <Row label="Claude Team (5 personas × $25 USD/mes)" value="~$125 USD/mes" sub="Pago anual ~$20/persona/mes. Verificar precio en México." />
          <Row label="Google Maps Routes Essentials" value="0 hasta 10k req/mes" sub="Después $5 USD / 1,000 solicitudes (hasta 100k). SKUs Pro y matrices cuestan más." />
          <Row label="AWS — referencia Lightsail" value="desde $5–10 USD/mes" sub="El costo real depende de arquitectura, BD, tráfico y región. Usar la calculadora de AWS." />
          <Row label="Google Play Developer" value="$25 USD pago único" sub="Para publicar en Android." />
          <Row label="Apple Developer (si lanzan iOS)" value="$99 USD/año" sub="Evaluar viabilidad técnica del notification listener en iOS primero." />
        </div>
      </div>

      <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden">
        <div className="px-4 py-3 border-b border-vygo-border">
          <p className="text-sm font-semibold text-vygo-white">Gastos de constitución (cotizar, no asumir)</p>
        </div>
        <div className="px-4 py-2">
          <Row label="Abogado corporativo (S.A.P.I. o S.A. de C.V.)" value="Cotizar" sub="Varía según tipo societario, socios y complejidad de estatutos." />
          <Row label="Notario" value="Cotizar" sub="Incluido en el proceso de constitución." />
          <Row label="Contador / setup fiscal inicial" value="Cotizar" sub="RFC, régimen, primera declaración." />
          <Row label="Marca VYGO en IMPI" value="~$2,695 MXN + IVA" sub="Por solicitud en línea. Confirmar al generar línea de captura. Puede ser más de una clase." />
          <Row label="Dominio y correo corporativo" value="~$20–50 USD/año" sub="Depende del proveedor y plan." />
        </div>
      </div>

      <div className="bg-vygo-card border border-vygo-border rounded-2xl overflow-hidden">
        <div className="px-4 py-3 border-b border-vygo-border">
          <p className="text-sm font-semibold text-vygo-white">Partidas que deben añadir al presupuesto</p>
        </div>
        <div className="px-4 py-2">
          <Row label="Base de datos (si no va en AWS)" value="Supabase Free o desde $25 USD/mes" />
          <Row label="Monitoreo y respaldos" value="Variable" />
          <Row label="Pasarela de pago" value="Comisión por transacción (Stripe, Conekta, etc.)" />
          <Row label="Comisión tiendas (si cobran en app)" value="Google Play 15–30% · App Store 15–30%" />
          <Row label="Pruebas con repartidores e incentivos" value="Presupuestar por piloto" />
          <Row label="Atención a usuarios" value="Tiempo del equipo o herramienta" />
          <Row label="Publicidad / adquisición de usuarios" value="Presupuestar separado" />
          <Row label="Sueldos o pago a fundadores" value="Definir antes de recibir inversión" />
          <Row label="Contabilidad mensual" value="Cotizar con contador" />
          <Row label="Asesoría de privacidad" value="Una vez + actualizaciones" />
        </div>
      </div>

      <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4">
        <p className="text-sm font-semibold text-vygo-white mb-2">Para calcular el costo real necesitamos:</p>
        <ul className="space-y-1.5 text-xs text-vygo-secondary list-disc list-inside">
          <li>Número de fundadores, aportación de cada uno, si algún inversionista ya propuso monto</li>
          <li>Cuántos asientos Claude Team / Premium usarán</li>
          <li>Arquitectura AWS prevista y si seguirán usando Supabase / Vercel / Render</li>
          <li>Usuarios esperados en piloto, mes 6 y mes 12</li>
          <li>Ofertas evaluadas por usuario al día y llamadas a Google Maps por oferta</li>
          <li>Horas de ubicación activa por usuario</li>
          <li>Si lanzarán solo Android, cómo cobrarán y cuánto planean pagar al equipo</li>
          <li>Gastos que ya conocen y dinero disponible hoy</li>
        </ul>
        <p className="text-xs text-vygo-green font-semibold mt-3">Con esos datos se puede armar: costo mensual, costo por repartidor activo y capital necesario para 6 y 12 meses.</p>
      </div>

      <div className="bg-vygo-card border border-vygo-border rounded-2xl p-4">
        <p className="text-[11px] font-semibold text-vygo-secondary uppercase tracking-wide mb-2">Fórmula de costo mensual</p>
        <div className="bg-vygo-card-2 rounded-xl p-3 font-mono text-[11px] text-vygo-white leading-relaxed">
          <p>costo_mes =</p>
          <p className="pl-4">herramientas_equipo</p>
          <p className="pl-4">+ infraestructura_fija</p>
          <p className="pl-4">+ (usuarios × consultas/usuario × costo_unitario)</p>
          <p className="pl-4">+ personal</p>
          <p className="pl-4">+ administración</p>
        </div>
        <p className="text-[11px] text-vygo-secondary mt-2">Google Maps cobra ciertos servicios por elemento de matriz, no por solicitud. Definir exactamente qué llamada hace el backend antes de proyectar ingresos.</p>
      </div>
    </div>
  )
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export function EmpresaPage() {
  const [activeTab, setActiveTab] = useState<Tab>('prioridades')

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Plan Empresa"
        showBack
        subtitle="Legal · Mercado · Presupuesto"
      />

      {/* Tab bar */}
      <div className="sticky top-0 z-10 bg-vygo-bg/95 backdrop-blur px-4 pb-3">
        <div className="grid grid-cols-4 gap-1 bg-vygo-card border border-vygo-border rounded-2xl p-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex flex-col items-center gap-1 py-2 rounded-xl text-[11px] font-semibold transition-all duration-200',
                activeTab === tab.id
                  ? 'bg-vygo-green text-white shadow-sm'
                  : 'text-vygo-secondary hover:text-vygo-white'
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="px-4 pb-8 animate-fade-in">
        {activeTab === 'prioridades' && <TabPrioridades />}
        {activeTab === 'legal'       && <TabLegal />}
        {activeTab === 'mercado'     && <TabMercado />}
        {activeTab === 'presupuesto' && <TabPresupuesto />}
      </div>

      <p className="text-center text-[11px] text-vygo-secondary/50 pb-6">
        Documento interno del equipo VYGO · {new Date().toLocaleDateString('es-MX', { year: 'numeric', month: 'long', day: 'numeric' })}
      </p>
    </div>
  )
}
