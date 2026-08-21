import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiClient } from "../api/client";
import { Mic } from "lucide-react";
import toast from "react-hot-toast";

const schema = z.object({
  full_name: z.string().min(2),
  email:     z.string().email(),
  password:  z.string().min(8).regex(/[A-Z]/, "Needs uppercase").regex(/\d/, "Needs a digit"),
});

type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    try {
      await apiClient.post("/auth/register", data);
      toast.success("Account created! Please sign in.");
      navigate("/login");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Registration failed");
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center mb-3 shadow-glow">
            <Mic size={22} className="text-white" />
          </div>
          <h1 className="text-xl font-semibold text-primary">Create Account</h1>
          <p className="text-sm text-muted mt-1">Start your interview prep journey</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {[
            { name: "full_name", label: "Full Name",     type: "text",     placeholder: "Jane Smith" },
            { name: "email",     label: "Email",          type: "email",    placeholder: "you@company.com" },
            { name: "password",  label: "Password",       type: "password", placeholder: "Min 8 chars, 1 uppercase, 1 number" },
          ].map(({ name, label, type, placeholder }) => (
            <div key={name}>
              <label className="text-xs text-muted block mb-1">{label}</label>
              <input
                {...register(name as any)}
                type={type}
                placeholder={placeholder}
                className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
              />
              {(errors as any)[name] && (
                <p className="text-xs text-error mt-1">{(errors as any)[name].message}</p>
              )}
            </div>
          ))}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center"
          >
            {isSubmitting ? (
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : "Create Account — Free"}
          </button>

          <p className="text-center text-xs text-muted">
            By registering, you agree to our Terms of Service and Privacy Policy.
          </p>
        </form>

        <p className="text-center text-xs text-muted mt-4">
          Already have an account?{" "}
          <Link to="/login" className="text-accent hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
