import { Terminal, BarChart3 } from 'lucide-react';

export const TransparentRationaleSection = () => {
  const indicators = [
    { label: "Technical: Oversold (RSI < 35)" },
    { label: "Momentum: MACD Bullish Crossover" },
    { label: "Fundamental: Positive Sentiment" },
  ];

  return (
    <div className="flex flex-col max-w-6xl w-[1152px] items-center gap-16 pt-32 pb-0 px-8 relative flex-[0_0_auto]">
      <div className="flex flex-col items-start gap-4 relative self-stretch w-full flex-[0_0_auto]">
        <div className="flex flex-col items-center relative self-stretch w-full flex-[0_0_auto]">
          <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Newsreader-Regular',Helvetica] font-normal text-gray-900 text-5xl text-center tracking-[0] leading-[48px] flex items-center whitespace-nowrap">
            Transparent Rationale
          </div>
        </div>
        <div className="flex flex-col items-center relative self-stretch w-full flex-[0_0_auto]">
          <div className="relative flex items-center justify-center w-fit mt-[-1.00px] [font-family:'Inter-Regular',Helvetica] font-normal text-[#11182780] text-base text-center tracking-[0] leading-6 whitespace-nowrap">
            สัมผัสเบื้องลึกกระบวนการตัดสินใจของ AI แบบเรียลไทม์
          </div>
        </div>
      </div>
      <div className="flex flex-col max-w-4xl w-[904px] items-start p-12 relative flex-[0_0_auto] mb-[-4.00px] bg-[#ffffffd9] rounded-[40px] overflow-hidden border-4 border-solid border-[#824199] shadow-[0px_20px_54px_#0000000d] backdrop-blur-[10px] backdrop-brightness-[100%] [-webkit-backdrop-filter:blur(10px)_brightness(100%)]">
        <div className="inline-flex flex-col items-start pl-[27.67px] pr-[25.17px] pt-[20.55px] pb-[32.29px] absolute top-px right-[9px]">
          <Terminal size={16} color="white" />
        </div>
        <div className="flex flex-col items-start gap-12 relative self-stretch w-full flex-[0_0_auto]">
          <div className="flex items-center justify-between relative self-stretch w-full flex-[0_0_auto]">
            <div className="inline-flex items-center gap-6 relative flex-[0_0_auto]">
              <div className="inline-flex flex-col items-start px-8 py-3 flex-[0_0_auto] bg-emerald-500 relative rounded-2xl">
                <div className="absolute w-full h-full top-0 left-0 bg-[#ffffff01] rounded-2xl shadow-[0px_4px_6px_-4px_#10b98133,0px_10px_15px_-3px_#10b98133]" />
                <div className="relative w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-white text-xl tracking-[1.00px] leading-7 flex items-center whitespace-nowrap">
                  BUY
                </div>
              </div>
              <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
                <div className="flex flex-col items-start relative self-stretch w-full flex-[0_0_auto]">
                  <div className="relative flex items-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-[#11182766] text-[10px] tracking-[1.00px] leading-[15px] whitespace-nowrap">
                    PROVIDER : AI
                  </div>
                </div>
                <div className="flex flex-col items-start relative self-stretch w-full flex-[0_0_auto]">
                  <div className="relative flex items-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-xl tracking-[0] leading-7 whitespace-nowrap">
                    THAI GOLD 96.5%
                  </div>
                </div>
              </div>
            </div>
            <div className="inline-flex flex-col items-end relative flex-[0_0_auto]">
              <div className="inline-flex flex-col items-center justify-center gap-2.5 relative flex-[0_0_auto]">
                <div className="relative flex items-center justify-center w-[172px] mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-[#11182766] text-[10px] text-center tracking-[1.00px] leading-[15px]">
                  CONFIDENCE SCORE
                </div>
              </div>
              <div className="relative w-[115px] h-10">
                <div className="absolute top-1.5 left-0 h-10 [font-family:'Newsreader-SemiBold',Helvetica] font-semibold text-[#824199] text-4xl tracking-[0] leading-10 flex items-center whitespace-nowrap">
                  85%
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-start gap-6 p-8 relative self-stretch w-full flex-[0_0_auto] bg-[#11182708] rounded-3xl border border-solid border-[#1118270d] backdrop-blur-[6px] backdrop-brightness-[100%] [-webkit-backdrop-filter:blur(6px)_brightness(100%)]">
            <div className="flex items-center gap-3 relative self-stretch w-full flex-[0_0_auto]">
              <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
                <BarChart3 size={20} className="text-purple-300" />
              </div>
              <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
                <div className="relative flex items-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-sm tracking-[1.40px] leading-5 whitespace-nowrap">
                  AI AGENT REASONING SYSTEM
                </div>
              </div>
            </div>
            <div className="flex flex-col items-start gap-4 relative self-stretch w-full flex-[0_0_auto]">
              <div className="flex flex-col items-start relative self-stretch w-full flex-[0_0_auto]">
                <p className="relative flex items-center self-stretch mt-[-1.00px] [font-family:'Newsreader-Regular',Helvetica] font-normal text-transparent text-2xl tracking-[0] leading-6">
                  <span className="[font-family:'Newsreader-Italic',Helvetica] italic text-gray-900 leading-[39px]">
                    &#34;Signal:{" "}
                  </span>
                  <span className="[font-family:'Newsreader-SemiBold',Helvetica] font-semibold text-emerald-600">
                    BUY{" "}
                  </span>
                  <span className="[font-family:'Newsreader-Italic',Helvetica] italic text-gray-900 leading-[39px]">
                    - Rationale: Technicals confirm strong upward momentum. RSI
                    has entered the oversold territory (&lt; 35), and MACD
                    exhibits a clear bullish divergence. Concurrently, FinBERT
                    sentiment analysis of recent Fed policy news indicates a
                    highly favorable macroeconomic environment for gold.&#34;
                  </span>
                </p>
              </div>
              <div className="grid grid-cols-3 grid-rows-[16px] h-fit gap-6 pt-6 pb-0 px-0 border-t [border-top-style:solid] border-[#1118271a]">
                {indicators.map((indicator, index) => (
                  <div
                    key={index}
                    className="relative row-[1_/_2] w-full h-4 flex items-center gap-3"
                  >
                    <div className="relative w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                    <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
                      <p className="relative flex items-center w-fit mt-[-1.00px] [font-family:'Inter-Medium',Helvetica] font-medium text-[#11182780] text-xs tracking-[0] leading-4 whitespace-nowrap">
                        {indicator.label}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
