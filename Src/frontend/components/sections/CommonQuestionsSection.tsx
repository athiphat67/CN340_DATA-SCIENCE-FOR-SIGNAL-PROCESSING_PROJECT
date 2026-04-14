import { useState } from "react";

const faqData = [
  {
    id: 1,
    question: "How accurate are the AI signals?",
  },
  {
    id: 2,
    question: "Is my wallet data secure?",
  },
  {
    id: 3,
    question: "Can I cancel my subscription anytime?",
  },
];

export const CommonQuestionsSection = () => {
  const [openId, setOpenId] = useState<number | null>(null);

  const handleToggle = (id: number) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="flex flex-col max-w-screen-md w-[768px] items-start gap-16 pt-[149px] pb-36 px-8 relative flex-[0_0_auto]">
      <div className="flex flex-col items-center relative self-stretch w-full flex-[0_0_auto]">
        <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Newsreader-Regular',Helvetica] font-normal text-gray-900 text-4xl text-center tracking-[0] leading-10 flex items-center whitespace-nowrap">
          Common Questions
        </div>
      </div>
      <div className="flex flex-col items-start gap-4 relative self-stretch w-full flex-[0_0_auto]">
        {faqData.map((item) => (
          <div
            key={item.id}
            className="flex flex-col items-start self-stretch w-full flex-[0_0_auto] bg-white overflow-hidden border border-solid border-gray-100 relative rounded-2xl"
          >
            <button
              type="button"
              className="flex items-center justify-between p-6 relative self-stretch w-full flex-[0_0_auto] text-left"
              onClick={() => handleToggle(item.id)}
              aria-expanded={openId === item.id}
            >
              <div className="inline-flex items-start flex-col relative flex-[0_0_auto]">
                <p className="relative w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-gray-900 text-base tracking-[0] leading-6 flex items-center whitespace-nowrap">
                  {item.question}
                </p>
              </div>
              <div className="inline-flex flex-col items-start relative flex-[0_0_auto]">
              </div>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
