import { cleanMarkdown, stripNoisyTextLabels, formatFlattenedCode } from './markdownRenderer.js';

const input = "text // 電燈問題的行動策略實現示例 (非程式碼，僅用數學表示) public class LightControl { // 定義狀態和動作 enum State { ON, OFF } enum Action { TURN_ON, TURN_OFF }";

console.log("--- Input ---");
console.log(input);

console.log("\n--- stripNoisyTextLabels ---");
const stripped = stripNoisyTextLabels(input);
console.log(stripped);

console.log("\n--- formatFlattenedCode ---");
const formatted = formatFlattenedCode(stripped);
console.log(formatted);

console.log("\n--- cleanMarkdown (Full Pipeline) ---");
const cleaned = cleanMarkdown(input);
console.log(cleaned);
