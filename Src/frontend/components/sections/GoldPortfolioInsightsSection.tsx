import { BrainCircuit, ShieldCheck, LineChart, Eye } from 'lucide-react';

const cards = [
  {
    icon: BrainCircuit,
    iconClass: "relative w-[19.01px] h-5",
    title: "Advanced\nReasoning",
    description:
      "ก้าวข้ามบอทตั้งเงื่อนไขทั่วไป สู่การ\nวิเคราะห์ตลาดแบบองค์รวมด้วย\nความฉลาดของ LLM",
    colClass: "col-[1_/_2]",
    heightClass: "h-fit",
    paddingClass: "pt-8 pb-[54.75px] px-8",
    alignSelf: "",
    titlePaddingTop: "pt-[9px]",
    descPaddingBottom: "pb-[0.75px]",
  },
  {
    icon: ShieldCheck,
    iconClass: "relative w-4 h-5",
    title: "Ironclad Risk\nManagement",
    description:
      "คำนวณ SL/TP อัตโนมัติตามค่า\nความผันผวนตลาด (ATR) พร้อม\nระบบคุมขีดจำกัดขาดทุนรายวัน",
    colClass: "col-[2_/_3]",
    heightClass: "h-[301px]",
    paddingClass: "p-8",
    alignSelf: "[align-self:start]",
    titlePaddingTop: "pt-[9.1px]",
    descPaddingBottom: "pb-[0.62px]",
  },
  {
    icon: LineChart,
    iconClass: "relative w-[18px] h-[18px]",
    title: "Technical &\nFundamental",
    description:
      "ผสานสัญญาณเชิงเทคนิคเข้ากับการ\nวิเคราะห์ Sentiment ข่าวเศรษฐกิจ\nโลกแบบ Real-time",
    colClass: "col-[3_/_4]",
    heightClass: "h-[302px]",
    paddingClass: "pt-8 pb-[54.75px] px-8",
    alignSelf: "[align-self:start]",
    titlePaddingTop: "pt-[9px]",
    descPaddingBottom: "pb-[0.75px]",
  },
  {
    icon: Eye,
    iconClass: "relative w-[22px] h-[15px]",
    title: "24/5 Vigilance",
    description:
      "เฝ้าระวังพอร์ตตลอดเวลาทำการ\nพร้อมระบบหลบหลีกช่วง \nDead Zone เพื่อปกป้องเงินทุน",
    colClass: "col-[4_/_5]",
    heightClass: "h-[302px]",
    paddingClass: "pt-8 pb-[60px] px-8",
    alignSelf: "[align-self:start]",
    titlePaddingTop: "pt-[9.1px]",
    descPaddingBottom: "pb-[0.62px]",
  },
];

export const GoldPortfolioInsightsSection = () => {
  return (
    <div className="flex flex-col max-w-screen-xl items-start gap-[21px] pt-[125px] pb-5 px-8 relative w-full flex-[0_0_auto]">
      <div className="flex items-end justify-around gap-[378.95px] relative self-stretch w-full flex-[0_0_auto]">
        <div className="inline-flex flex-col max-w-xl items-start pl-0 pr-[112.92px] py-0 relative flex-[0_0_auto]">
          <p className="relative w-fit mt-[-1.00px] [font-family:'Newsreader-Regular',Helvetica] font-normal text-transparent text-5xl tracking-[0] leading-[48px]">
            <span className="text-gray-900">
              Smarter decisions <br />
              for{" "}
            </span>
            <span className="[font-family:'Newsreader-Italic',Helvetica] italic text-[#824199]">
              gold
            </span>
            <span className="text-gray-900"> portfolio</span>
          </p>
        </div>
      </div>
      <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
        <p className="relative flex items-center w-fit mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182780] text-sm tracking-[0] leading-5 whitespace-nowrap">
          Data-driven logic in every single trade.
        </p>
      </div>
      <div className="grid grid-cols-4 grid-rows-[346.50px] h-fit gap-6">
        {cards.map((card, index) => (
          <div
            key={index}
            className={`${card.colClass} ${card.alignSelf} ${card.heightClass} gap-[15px] ${card.paddingClass} relative row-[1_/_2] w-full flex flex-col items-start bg-[#ffffffcc] rounded-3xl border border-solid border-[#ffffff80] shadow-[0px_20px_50px_#0000000d] backdrop-blur-[5px] backdrop-brightness-[100%] [-webkit-backdrop-filter:blur(5px)_brightness(100%)]`}
          >
            <div className="flex w-12 h-12 items-center justify-center relative bg-[#8241991a] rounded-xl">
              <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
                <img className={card.iconClass} alt="Icon" src={card.icon} />
              </div>
            </div>
            <div
              className={`flex items-start ${card.titlePaddingTop} pb-0 px-0 self-stretch w-full flex-col relative flex-[0_0_auto]`}
            >
              <div className="relative self-stretch mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-xl tracking-[0] leading-7">
                {card.title.split("\n").map((line, i, arr) => (
                  <span key={i}>
                    {line}
                    {i < arr.length - 1 && <br />}
                  </span>
                ))}
              </div>
            </div>
            <div
              className={`flex flex-col items-start pt-0 ${card.descPaddingBottom} px-0 relative self-stretch w-full flex-[0_0_auto]`}
            >
              <div className="relative self-stretch mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182799] text-sm tracking-[0] leading-[22.8px]">
                {card.description.split("\n").map((line, i, arr) => (
                  <span key={i}>
                    {line}
                    {i < arr.length - 1 && <br />}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
