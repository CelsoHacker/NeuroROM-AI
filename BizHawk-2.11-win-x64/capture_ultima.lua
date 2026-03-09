local function apply_state(state)
  if joypad and joypad.set then
    pcall(function() joypad.set(1, state) end)
    pcall(function() joypad.set(state) end)
  end
end

local function screenshot(name)
  if client and client.screenshot then
    pcall(function() client.screenshot('captures_auto/' .. name) end)
  end
end

local function press_b1(state)
  state['P1 B1']=true
  state['B1']=true
  state['1']=true
end

local function press_b2(state)
  state['P1 B2']=true
  state['B2']=true
  state['2']=true
end

for i=0,4200 do
  local state = {}

  -- titulo -> menu
  if (i>=220 and i<=230) then
    press_b1(state)
  end

  -- menu -> novo jogo
  if (i>=500 and i<=510) then
    press_b1(state)
  end

  -- nome: escolhe 'A' usando B2
  if (i>=650 and i<=656) then
    press_b2(state)
  end

  -- desce 4 linhas
  if (i>=720 and i<=726) or (i>=770 and i<=776) or (i>=820 and i<=826) or (i>=870 and i<=876) then
    state['P1 Down']=true
    state['Down']=true
  end

  -- direita 11 colunas ate END
  local right_bursts = {
    {950,956},{980,986},{1010,1016},{1040,1046},{1070,1076},{1100,1106},
    {1130,1136},{1160,1166},{1190,1196},{1220,1226},{1250,1256}
  }
  for _,r in ipairs(right_bursts) do
    if i>=r[1] and i<=r[2] then
      state['P1 Right']=true
      state['Right']=true
    end
  end

  -- confirma END usando B2
  if (i>=1320 and i<=1340) then
    press_b2(state)
  end

  -- avanca dialogos posteriores (B1+B2)
  if (i>=1500 and i<=1510) or (i>=1700 and i<=1710) or (i>=1900 and i<=1910) or (i>=2100 and i<=2110) or (i>=2300 and i<=2310) or (i>=2500 and i<=2510) or (i>=2700 and i<=2710) or (i>=2900 and i<=2910) or (i>=3100 and i<=3110) or (i>=3300 and i<=3310) or (i>=3500 and i<=3510) or (i>=3700 and i<=3710) or (i>=3900 and i<=3910) then
    press_b1(state)
    press_b2(state)
  end

  apply_state(state)

  if i % 100 == 0 then
    local name = string.format('fix6_f%05d.png', i)
    screenshot(name)
  end

  emu.frameadvance()
end

apply_state({})
if client and client.exit then
  pcall(function() client.exit() end)
end
