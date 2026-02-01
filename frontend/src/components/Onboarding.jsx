import { useIsMobile } from "../hooks/useMediaQuery";
import { OnboardingMobile } from "./OnboardingMobile";
import { OnboardingDesktop } from "./OnboardingDesktop";

export function Onboarding() {
  const isMobile = useIsMobile();
  return isMobile ? <OnboardingMobile /> : <OnboardingDesktop />;
}
