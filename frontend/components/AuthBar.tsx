"use client";

import { useAuth, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";

export function AuthBar() {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) return <div className="h-10 border-b border-gray-100" />;

  if (isSignedIn) {
    return (
      <div className="flex items-center justify-end gap-3 border-b border-gray-100 px-6 py-2">
        <UserButton
          appearance={{
            elements: {
              avatarBox: "h-8 w-8",
            },
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-end gap-3 border-b border-gray-100 px-6 py-2">
      <SignInButton>
        <button className="rounded-lg px-4 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100">
          登录
        </button>
      </SignInButton>
      <SignUpButton>
        <button className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700">
          注册
        </button>
      </SignUpButton>
    </div>
  );
}
