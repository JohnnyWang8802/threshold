SRC ?= input/source.png

all: still grid web video

still:   ## 渲染静态数字画（PNG）
	python3 src/mosaic.py --src $(SRC) --out out/still.png

grid:    ## 提取动画用的色调网格
	python3 src/export_grid.py --src $(SRC) --out out/grid.json

web: grid ## 生成可交互的单文件网页
	python3 src/build_web.py --grid out/grid.json --tpl web/app.html --out out/live.html

video: grid ## 渲染 MP4
	python3 src/render_video.py --grid out/grid.json --out out/threshold.mp4

clean:
	rm -f out/*

.PHONY: all still grid web video clean
