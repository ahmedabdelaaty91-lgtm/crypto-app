//@version=5
indicator("Swing Trade Pros - Auto Trend Lines Touch", overlay=true)

leftBars = input.int(7, "Left Bars (قوة القاع)")
rightBars = input.int(3, "Right Bars")

pl = ta.pivotlow(low, leftBars, rightBars)

var float pl1 = na
var int pl1_x = na
var float pl2 = na
var int pl2_x = na

if not na(pl)
    pl1 := pl2
    pl1_x := pl2_x
    pl2 := pl
    pl2_x := bar_index - rightBars

var line greenLine = na
float greenLineVal = na

if not na(pl1) and not na(pl2) and pl2_x > pl1_x
    slope = (pl2 - pl1) / (pl2_x - pl1_x)
    greenLineVal := pl2 + slope * (bar_index - pl2_x)
    line.delete(greenLine)
    greenLine := line.new(pl1_x, pl1, bar_index + 12, pl2 + slope * (bar_index + 12 - pl2_x), color=color.green, width=2)

// شرط ملامسة الخط الأخضر
touch_green = not na(greenLineVal) and low <= (greenLineVal * 1.008) and low >= (greenLineVal * 0.985) and close >= greenLineVal

plotshape(touch_green, title="لمس الأخضر", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small, text="ملامسة الترند")
alertcondition(touch_green, title="ملامسة خط الترند الأخضر", message="🟢 تنبيه: السعر لامس خط الدعم الأخضر على {{ticker}} في فريم {{interval}}!")
