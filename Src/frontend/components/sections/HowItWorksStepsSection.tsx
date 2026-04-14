import { Database, Brain, ShieldAlert, Zap } from 'lucide-react';

const steps = [
  {
    icon: Database,
    iconClass: "relative w-[30px] h-[28.75px]",
    bgColor: "bg-[#f5e6fa]",
    step: "STEP 1",
    title: "Data Ingestion",
    description: (
      <>
        ดึงราคาทองคำ XAU/USD, <br />
        อินดิเคเตอร์ทางเทคนิค และประเมิน Sentiment <br />
        ข่าวเศรษฐกิจโลก 8 หมวดหมู่แบบเรียลไทม์
      </>
    ),
    descriptionClass:
      "relative w-fit mt-[-1.00px] ml-[-6.50px] mr-[-6.50px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182799] text-xs text-center tracking-[0] leading-[19.5px]",
    showConnector: true,
  },
  {
    icon: Brain,
    iconClass: "relative w-[23.79px] h-[25px]",
    bgColor: "bg-[#fef9e7]",
    step: "STEP 2",
    title: "AI Brain & ReAct Loop",
    titleIsP: true,
    description: (
      <>
        สมองกล AI วิเคราะห์สถานการณ์
        <br />
        และเลือกใช้เครื่องมือซ้ำแล้วซ้ำเล่า <br />
        จนกว่าจะมั่นใจมากที่สุด ก่อนตัดสินใจ
      </>
    ),
    descriptionClass:
      "relative w-fit mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182799] text-xs text-center tracking-[0] leading-[19.5px]",
    showConnector: true,
  },
  {
    icon: ShieldAlert,
    iconClass: "relative w-5 h-[25px]",
    bgColor: "bg-[#f5e6fa]",
    step: "STEP 3",
    title: "Risk Gate",
    description: (
      <>
        ตรวจสอบเวลาเปิด-ปิดตลาด, <br />
        ล็อกเพดานขาดทุนรายวัน และคำนวณ SL/TP <br />
        อัตโนมัติด้วยค่าความผันผวนจริง (ATR)
      </>
    ),
    descriptionClass:
      "relative w-fit mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182799] text-xs text-center tracking-[0] leading-[19.5px]",
    showConnector: true,
  },
  {
    icon: Zap,
    iconClass: "relative w-[27.5px] h-[21.3px]",
    bgColor: "bg-[#fef9e7]",
    step: "STEP 4",
    title: "Insightful Execution",
    description: (
      <>
        ส่งคำสั่งอัตโนมัติพร้อมแจ้งเตือนผ่านระบบ <br />
        โดยอธิบายลอจิกและเหตุผลเบื้องหลัง
        <br />
        ทุกการตัดสินใจอย่างโปร่งใส
      </>
    ),
    descriptionClass:
      "relative w-fit mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182799] text-xs text-center tracking-[0] leading-[19.5px]",
    showConnector: false,
    isLast: true,
  },
];

export const HowItWorksStepsSection = () => {
  return (
    <div className="flex flex-col items-start pt-24 pb-[50px] px-8 relative self-stretch w-full flex-[0_0_auto] bg-[#ffffff4c] backdrop-blur-[2px] backdrop-brightness-[100%] [-webkit-backdrop-filter:blur(2px)_brightness(100%)]">
      <div className="flex flex-col max-w-6xl items-start gap-16 px-8 py-0 relative w-full flex-[0_0_auto]">
        <div className="flex flex-col items-start gap-4 relative self-stretch w-full flex-[0_0_auto]">
          <div className="flex items-center self-stretch w-full flex-col relative flex-[0_0_auto]">
            <p className="relative flex items-center justify-center w-fit mt-[-1.00px] [font-family:'Newsreader-Regular',Helvetica] font-normal text-transparent text-5xl text-center tracking-[0] leading-[48px] whitespace-nowrap">
              <span className="text-gray-900">How it </span>
              <span className="text-[#824199]">Works</span>
            </p>
          </div>
          <div className="flex flex-col items-center relative self-stretch w-full flex-[0_0_auto]">
            <p className="relative flex items-center justify-center w-fit mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182780] text-base text-center tracking-[0] leading-6 whitespace-nowrap">
              Our multi-layered AI architecture ensures precision and speed.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-4 grid-rows-[229px] h-fit gap-8">
          {steps.map((step, index) => {
            if (step.isLast) {
              return (
                <div
                  key={index}
                  className="col-[4_/_5] items-center gap-2 px-4 py-0 relative row-[1_/_2] w-full h-fit flex flex-col"
                >
                  <div
                    className={`flex w-16 h-16 items-center justify-center ${step.bgColor} shadow-[0px_1px_2px_#0000000d] relative rounded-2xl`}
                  >
                    <div className="inline-flex flex-col items-center relative flex-[0_0_auto]">
                      <img
                        className={step.iconClass}
                        alt="Icon"
                        src={step.icon}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col items-center pt-4 pb-0 px-0 relative self-stretch w-full flex-[0_0_auto]">
                    <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-[#82419966] text-[10px] text-center tracking-[1.00px] leading-[15px] flex items-center whitespace-nowrap">
                      {step.step}
                    </div>
                  </div>
                  <div className="flex items-center self-stretch w-full flex-col relative flex-[0_0_auto]">
                    <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-lg text-center tracking-[0] leading-7 flex items-center whitespace-nowrap">
                      {step.title}
                    </div>
                  </div>
                  <div className="flex flex-col items-center pt-1 pb-0 px-0 relative self-stretch w-full flex-[0_0_auto]">
                    <div className={step.descriptionClass}>
                      {step.description}
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={index}
                className={`col-[${index + 1}_/_${index + 2}] items-start relative row-[1_/_2] w-full h-fit flex flex-col`}
              >
                <div className="flex flex-col items-center gap-2 px-4 py-0 relative self-stretch w-full flex-[0_0_auto]">
                  <div
                    className={`flex w-16 h-16 items-center justify-center ${step.bgColor} shadow-[0px_1px_2px_#0000000d] relative rounded-2xl`}
                  >
                    <div className="inline-flex flex-col items-center relative flex-[0_0_auto]">
                      <img
                        className={step.iconClass}
                        alt="Icon"
                        src={step.icon}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col items-center pt-4 pb-0 px-0 relative self-stretch w-full flex-[0_0_auto]">
                    <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-[#82419966] text-[10px] text-center tracking-[1.00px] leading-[15px] flex items-center whitespace-nowrap">
                      {step.step}
                    </div>
                  </div>
                  <div className="flex flex-col items-center relative self-stretch w-full flex-[0_0_auto]">
                    {step.titleIsP ? (
                      <p className="relative justify-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-lg text-center tracking-[0] leading-7 flex items-center whitespace-nowrap">
                        {step.title}
                      </p>
                    ) : (
                      <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-lg text-center tracking-[0] leading-7 flex items-center whitespace-nowrap">
                        {step.title}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-center pt-1 pb-0 px-0 relative self-stretch w-full flex-[0_0_auto]">
                    <p className={step.descriptionClass}>{step.description}</p>
                  </div>
                </div>
                {step.showConnector && (
                  <div className="absolute top-8 -right-4 w-8 h-0.5 border-t-2 [border-top-style:dashed] border-[#82419933]" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
