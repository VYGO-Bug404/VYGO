import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <div className="flex justify-center items-start lg:items-center w-full h-full bg-vygo-bg lg:bg-[#0E1145] relative overflow-hidden">

      {/* Desktop decorations */}
      <div className="hidden lg:block pointer-events-none select-none">
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full bg-[#C9E86E]/5 blur-[120px]" />
        <div className="absolute bottom-1/3 right-1/4 w-[350px] h-[350px] rounded-full bg-[#6FA800]/6 blur-[100px]" />
        <div className="absolute bottom-10 left-12">
          <p className="text-[#3A4090] text-xs font-medium tracking-wide uppercase">
            DeliveryTech · Monterrey
          </p>
        </div>
      </div>

      {/* Phone frame */}
      <div
        className={[
          'relative flex flex-col w-full max-w-[430px] h-full overflow-hidden bg-vygo-bg',
          'lg:w-[390px] lg:max-w-none lg:h-[min(844px,calc(100vh-40px))]',
          'lg:rounded-[52px] lg:border-[10px] lg:border-[#1a1f6e]',
          'lg:shadow-phone',
        ].join(' ')}
      >
        {/* Dynamic island */}
        <div className="hidden lg:flex absolute top-3 left-1/2 -translate-x-1/2 z-50
                        w-[110px] h-[30px] bg-[#0F1340] rounded-full
                        items-center justify-center gap-2 pointer-events-none">
          <div className="w-2 h-2 rounded-full bg-[#1a2055]" />
          <div className="w-5 h-1.5 rounded-full bg-[#1a2055]" />
        </div>

        {/* Side buttons */}
        <div className="hidden lg:block absolute left-[-18px] top-28 w-[8px] h-10 bg-[#141860] rounded-l-md" />
        <div className="hidden lg:block absolute left-[-18px] top-44 w-[8px] h-14 bg-[#141860] rounded-l-md" />
        <div className="hidden lg:block absolute right-[-18px] top-36 w-[8px] h-20 bg-[#141860] rounded-r-md" />

        <div className="flex-1 overflow-y-auto scrollbar-none lg:pt-10">
          <Outlet />
        </div>

        {/* Home indicator */}
        <div className="hidden lg:flex justify-center py-2 bg-vygo-bg shrink-0">
          <div className="w-32 h-1 bg-vygo-border rounded-full" />
        </div>
      </div>
    </div>
  )
}
