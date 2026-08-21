import { useNavigate, Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useStore } from "../store";
import { apiClient } from "../api/client";
import { Mic } from "lucide-react";
import toast from "react-hot-toast";

const schema = z.object({
  email:    z.string().email(),
  password: z.string().min(1),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const { setUser } = useStore();
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    try {
      const { data: res }  = await apiClient.post("/auth/login", data);
      const { data: user } = await apiClient.get("/auth/me", {
        headers: { Authorization: `Bearer ${res.access_token}` },
      });
      setUser(user, res.access_token);
      navigate("/dashboard");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Login failed");
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center mb-3 shadow-glow">
            <Mic size={22} className="text-white" />
          </div>
          <h1 className="text-xl font-semibold text-primary">InterviewCopilot AI</h1>
          <p className="text-sm text-muted mt-1">Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="text-xs text-muted block mb-1">Email</label>
            <input
              {...register("email")}
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
            />
            {errors.email && <p className="text-xs text-error mt-1">{errors.email.message}</p>}
          </div>

          <div>
            <label className="text-xs text-muted block mb-1">Password</label>
            <input
              {...register("password")}
              type="password"
              placeholder="••••••••"
              autoComplete="current-password"
              className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center"
          >
            {isSubmitting ? (
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : "Sign In"}
          </button>
        </form>

        <p className="text-center text-xs text-muted mt-6">
          Don't have an account?{" "}
          <Link to="/register" className="text-accent hover:underline">Create one free</Link>
        </p>
      </div>
    </div>
  );
}
