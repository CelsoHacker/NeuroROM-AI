local log_path = [[captures_auto/capture_smoke.log]]
local function log(msg)
  local f = io.open(log_path, 'a')
  if f then f:write(msg .. "\n"); f:close() end
end
log('start')
for i=1,180 do emu.frameadvance() end
local saved=false
if client and client.screenshot then
  local ok, err = pcall(function() client.screenshot('captures_auto/screen_client.png') end)
  log('client.screenshot ok=' .. tostring(ok) .. ' err=' .. tostring(err))
  if ok then saved=true end
end
if (not saved) and gui and gui.savescreenshotas then
  local ok, err = pcall(function() gui.savescreenshotas('captures_auto/screen_gui.png') end)
  log('gui.savescreenshotas ok=' .. tostring(ok) .. ' err=' .. tostring(err))
  if ok then saved=true end
end
log('saved=' .. tostring(saved))
if client and client.exit then pcall(function() client.exit() end) end
