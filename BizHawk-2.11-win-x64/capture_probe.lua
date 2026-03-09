local f = io.open('captures_auto/probe.txt','w')
if f then f:write('probe_ok\n'); f:close() end
if client and client.screenshot then
  pcall(function() client.screenshot('captures_auto/probe.png') end)
end
if client and client.exit then pcall(function() client.exit() end) end
