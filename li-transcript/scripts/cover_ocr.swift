// 封面/截图文字识别（macOS 系统自带 Vision，zh-Hans + en-US）
// 用法: swiftc cover_ocr.swift -o /tmp/ocr  (首次/缺失时编译)
//       /tmp/ocr <图片路径>
// 输出: 逐行识别文字，带 [y=.. x=..] 坐标（y 越大越靠上，同 y 内 x 从左到右）；
//       图片打不开时打印「无法加载图片」。
// 说明: 本环境模型无视觉，封面花字不靠 AI 看图，一律用此工具，勿现场另写 OCR 脚本。
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else { exit(1) }
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("无法加载图片"); exit(1)
}
let request = VNRecognizeTextRequest { req, _ in
    guard let obs = req.results as? [VNRecognizedTextObservation] else { return }
    // 按 y 从上到下、同 y 内 x 从左到右排序
    let sorted = obs.sorted { a, b in
        let ay = a.boundingBox.midY, by = b.boundingBox.midY
        if abs(ay - by) > 0.02 { return ay > by }
        return a.boundingBox.minX < b.boundingBox.minX
    }
    for o in sorted {
        if let t = o.topCandidates(1).first {
            let box = o.boundingBox
            print("[y=\(String(format:"%.2f",box.midY)) x=\(String(format:"%.2f",box.minX))] \(t.string)")
        }
    }
}
request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en-US"]
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([request])
