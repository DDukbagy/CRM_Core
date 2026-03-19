import { createContext, useContext, useState, ReactNode } from "react";

type Ctx = { openModal: () => void; isOpen: boolean; close: () => void };

const CustomerRegisterContext = createContext<Ctx>({
  openModal: () => {},
  isOpen: false,
  close: () => {},
});

export function CustomerRegisterProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <CustomerRegisterContext.Provider
      value={{ openModal: () => setIsOpen(true), isOpen, close: () => setIsOpen(false) }}
    >
      {children}
    </CustomerRegisterContext.Provider>
  );
}

export const useCustomerRegister = () => useContext(CustomerRegisterContext);
