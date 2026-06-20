const routeArrowShapes = {
  viewBox: "0 0 1062 436",

  style: {
    mainColor: "#61A776",
    outlineColor: "#ffffff",
    mainStrokeWidth: 13,
    outlineStrokeWidth: 24
  },

  leftArrow: {
    // 左箭头版：线从箭头内部开始，不再从 [36,21] 开始
    linePoints: [
      [40, 46],
      [118, 247],
      [254, 319],
      [447, 347],
      [585, 335],
      [846, 317],
      [1033, 384]
    ],

    // 白色外描边箭头
    outlineArrowPoints: [
      [36, 21],
      [22.48, 77.43],
      [75.82, 68.90]
    ],

    // 绿色主体箭头
    mainArrowPoints: [
      [36, 21],
      [26.98, 58.62],
      [62.54, 52.93]
    ]
  },

  rightArrow: {
    // 右箭头版：线结束在箭头内部，不再画到 [1033,384]
    linePoints: [
      [36, 21],
      [118, 247],
      [254, 319],
      [447, 347],
      [585, 335],
      [846, 317],
      [1001, 384]
    ],

    // 白色外描边箭头
    outlineArrowPoints: [
      [1033, 384],
      [979, 357],
      [979, 411]
    ],

    // 绿色主体箭头
    mainArrowPoints: [
      [1033, 384],
      [991, 363],
      [991, 405]
    ]
  }
};

function pointsToPathD(points) {
  return points
    .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`)
    .join(" ");
}

function pointsToPolygon(points) {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

// 可选：直接生成 SVG 需要的数据
const leftArrowSvgData = {
  linePathD: pointsToPathD(routeArrowShapes.leftArrow.linePoints),
  outlineArrowPolygon: pointsToPolygon(routeArrowShapes.leftArrow.outlineArrowPoints),
  mainArrowPolygon: pointsToPolygon(routeArrowShapes.leftArrow.mainArrowPoints)
};

const rightArrowSvgData = {
  linePathD: pointsToPathD(routeArrowShapes.rightArrow.linePoints),
  outlineArrowPolygon: pointsToPolygon(routeArrowShapes.rightArrow.outlineArrowPoints),
  mainArrowPolygon: pointsToPolygon(routeArrowShapes.rightArrow.mainArrowPoints)
};

export default routeArrowShapes;
export { leftArrowSvgData, rightArrowSvgData };
