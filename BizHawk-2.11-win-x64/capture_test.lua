
for i=1,240 do
  if i==180 then
    if client and client.screenshot then
      pcall(function() client.screenshot('captures_auto/screen_client.png') end)
    end
    if gui and gui.savescreenshotas then
      pcall(function() gui.savescreenshotas('captures_auto/screen_gui.png') end)
    end
  end
  emu.frameadvance()
end
if client and client.exit then
  pcall(function() client.exit() end)
end
