import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <div className="flex justify-center w-full h-full bg-vygo-bg">
      <div className="relative w-full max-w-[430px] h-full flex flex-col overflow-hidden bg-vygo-bg">
        <div className="flex-1 overflow-y-auto scrollbar-none">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
