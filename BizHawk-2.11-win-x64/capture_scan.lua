local out_dir = 'C:/Users/celso/OneDrive/Área de Trabalho/PROJETO_V5_OFICIAL/rom-translation-framework/BizHawk-2.11-win-x64/captures_scan'
local log_path = 'C:/Users/celso/OneDrive/Área de Trabalho/PROJETO_V5_OFICIAL/rom-translation-framework/BizHawk-2.11-win-x64/captures_scan_log.txt'

local function log(msg)
  local f = io.open(log_path, 'a')
  if f then
    f:write(msg .. '\\n')
    f:close()
  end
end

local function screenshot(name)
  local path = out_dir .. '/' .. name
  local ok1 = false
  local ok2 = false
  if client and client.screenshot then
    ok1 = pcall(function() client.screenshot(path) end)
  end
  if gui and gui.savescreenshotas then
    ok2 = pcall(function() gui.savescreenshotas(path) end)
  end
  log('shot ' .. name .. ' client=' .. tostring(ok1) .. ' gui=' .. tostring(ok2))
end

log('start')
for i=0,12000 do
  if i % 800 == 0 then
    local name = string.format('f%05d.png', i)
    screenshot(name)
  end
  emu.frameadvance()
end
log('end')
if client and client.exit then
  pcall(function() client.exit() end)
end
